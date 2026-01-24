"""
音声バッファ管理モジュール
チャンク分割とキュー管理
"""
import queue
import threading
import time
from typing import Optional, Callable
import numpy as np
from src.utils.logger import logger
from src.audio.vad import VADProcessor


class AudioBufferManager:
    """
    音声チャンクのキュー管理クラス
    - Thread-safeなキュー実装
    - チャンク間隔の計測・分割
    - メモリ効率的な管理
    """

    def __init__(
        self,
        chunk_duration_sec: int = 30,
        sample_rate: int = 16000,
        channels: int = 1,
        on_chunk_ready: Optional[Callable[[bytes, float], None]] = None,
        vad_enabled: bool = False,
        vad_aggressiveness: int = 2
    ):
        """
        バッファマネージャの初期化

        Args:
            chunk_duration_sec: チャンク間隔（秒）
            sample_rate: サンプルレート
            channels: チャンネル数
            on_chunk_ready: チャンク準備完了時のコールバック関数
            vad_enabled: VADを有効化するか
            vad_aggressiveness: VAD感度（0-3）
        """
        self.chunk_duration_sec = chunk_duration_sec
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_chunk_ready = on_chunk_ready

        # チャンクサイズ（バイト数）
        # 16bit (2 bytes) * sample_rate * channels * duration
        self.chunk_size_bytes = 2 * sample_rate * channels * chunk_duration_sec

        # バッファ
        self.buffer = bytearray()
        self.buffer_lock = threading.Lock()

        # チャンク処理用キュー
        self.chunk_queue = queue.Queue(maxsize=100)

        # VAD
        self.vad_enabled = vad_enabled
        self.vad_processor = None
        if vad_enabled:
            self.vad_processor = VADProcessor(
                sample_rate=sample_rate,
                aggressiveness=vad_aggressiveness
            )
            if self.vad_processor.is_available():
                logger.info("VAD enabled")
            else:
                logger.warning("VAD requested but webrtcvad not available")
                self.vad_enabled = False

        # 統計情報
        self.total_chunks_processed = 0
        self.total_chunks_skipped = 0
        self.start_time = None

        # 処理スレッド
        self.processing_thread: Optional[threading.Thread] = None
        self.is_processing = False

        logger.info(
            f"AudioBufferManager initialized: "
            f"chunk_duration={chunk_duration_sec}s, "
            f"sample_rate={sample_rate}Hz, "
            f"chunk_size={self.chunk_size_bytes} bytes, "
            f"vad_enabled={vad_enabled}"
        )

    def add_audio_data(self, audio_data: bytes) -> None:
        """
        音声データをバッファに追加

        Args:
            audio_data: 音声データ（bytes）
        """
        with self.buffer_lock:
            self.buffer.extend(audio_data)

            # チャンクサイズに達したら分割
            while len(self.buffer) >= self.chunk_size_bytes:
                chunk = bytes(self.buffer[:self.chunk_size_bytes])
                self.buffer = self.buffer[self.chunk_size_bytes:]

                # チャンクのタイムスタンプ（録音開始からの経過時間）
                timestamp = self._get_current_timestamp()

                try:
                    self.chunk_queue.put_nowait((chunk, timestamp))
                    logger.debug(f"Chunk added to queue: {len(chunk)} bytes at {timestamp:.2f}s")
                except queue.Full:
                    logger.warning("Chunk queue is full, dropping oldest chunk")
                    try:
                        self.chunk_queue.get_nowait()  # 古いチャンクを削除
                        self.chunk_queue.put_nowait((chunk, timestamp))
                    except queue.Empty:
                        pass

    def _get_current_timestamp(self) -> float:
        """
        現在のタイムスタンプを取得（録音開始からの経過時間）

        Returns:
            経過時間（秒）
        """
        if self.start_time is None:
            self.start_time = time.time()
            return 0.0
        return time.time() - self.start_time

    def start_processing(self) -> None:
        """チャンク処理スレッドを開始"""
        if self.is_processing:
            logger.warning("Processing already started")
            return

        self.is_processing = True
        self.start_time = time.time()
        self.processing_thread = threading.Thread(
            target=self._process_chunks,
            daemon=True
        )
        self.processing_thread.start()
        logger.info("Chunk processing started")

    def stop_processing(self) -> None:
        """チャンク処理スレッドを停止"""
        if not self.is_processing:
            return

        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        logger.info("Chunk processing stopped")

    def _process_chunks(self) -> None:
        """チャンク処理のメインループ"""
        while self.is_processing:
            try:
                # タイムアウト付きでチャンクを取得
                chunk, timestamp = self.chunk_queue.get(timeout=1.0)

                # VADによる発話検出
                should_process = True
                if self.vad_enabled and self.vad_processor:
                    is_speech = self.vad_processor.is_speech(chunk)
                    if not is_speech:
                        logger.debug(f"Skipping silent chunk at {timestamp:.2f}s")
                        self.total_chunks_skipped += 1
                        should_process = False

                # コールバック関数を呼び出し
                if should_process and self.on_chunk_ready:
                    try:
                        self.on_chunk_ready(chunk, timestamp)
                        self.total_chunks_processed += 1
                    except Exception as e:
                        logger.error(f"Error in chunk callback: {e}")

                self.chunk_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")

    def get_buffer_size(self) -> int:
        """
        現在のバッファサイズを取得

        Returns:
            バッファサイズ（バイト数）
        """
        with self.buffer_lock:
            return len(self.buffer)

    def get_queue_size(self) -> int:
        """
        キューのサイズを取得

        Returns:
            キューのサイズ
        """
        return self.chunk_queue.qsize()

    def clear(self) -> None:
        """バッファとキューをクリア"""
        with self.buffer_lock:
            self.buffer.clear()

        while not self.chunk_queue.empty():
            try:
                self.chunk_queue.get_nowait()
                self.chunk_queue.task_done()
            except queue.Empty:
                break

        self.total_chunks_processed = 0
        self.total_chunks_skipped = 0
        self.start_time = None
        logger.info("Buffer and queue cleared")

    def get_stats(self) -> dict:
        """
        統計情報を取得

        Returns:
            統計情報の辞書
        """
        return {
            "buffer_size_bytes": self.get_buffer_size(),
            "queue_size": self.get_queue_size(),
            "total_chunks_processed": self.total_chunks_processed,
            "total_chunks_skipped": self.total_chunks_skipped,
            "elapsed_time_sec": self._get_current_timestamp() if self.start_time else 0.0
        }
