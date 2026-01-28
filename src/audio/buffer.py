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
        vad_aggressiveness: int = 2,
        queue_maxsize: int = 20,
        chunk_overlap_sec: int = 5
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
            queue_maxsize: キューの最大サイズ
            chunk_overlap_sec: チャンクオーバーラップ（秒）
        """
        self.chunk_duration_sec = chunk_duration_sec
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_chunk_ready = on_chunk_ready

        # チャンクサイズ（バイト数）
        # 16bit (2 bytes) * sample_rate * channels * duration
        self.chunk_size_bytes = 2 * sample_rate * channels * chunk_duration_sec

        # オーバーラップ設定
        self.overlap_duration_sec = chunk_overlap_sec
        self.overlap_size_bytes = 2 * sample_rate * channels * chunk_overlap_sec
        self.previous_overlap = bytearray()

        # バッファ
        self.buffer = bytearray()
        self.buffer_lock = threading.Lock()

        # チャンク処理用キュー
        self.chunk_queue = queue.Queue(maxsize=queue_maxsize)

        # VAD（完全遅延初期化 - 録音開始時に作成）
        self.vad_enabled = vad_enabled
        self.vad_processor = None
        self.vad_aggressiveness = vad_aggressiveness
        self._vad_initialized = False

        if vad_enabled:
            logger.info(f"VAD enabled (aggressiveness: {vad_aggressiveness}, will load on first use)")

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
                # 前チャンクのオーバーラップを含める
                chunk_with_overlap = bytes(self.previous_overlap + self.buffer[:self.chunk_size_bytes])

                # 次回用のオーバーラップを保存（最後のN秒）
                if self.overlap_size_bytes > 0:
                    overlap_start = max(0, self.chunk_size_bytes - self.overlap_size_bytes)
                    self.previous_overlap = self.buffer[overlap_start:self.chunk_size_bytes]

                # インプレース削除でメモリコピーを削減
                del self.buffer[:self.chunk_size_bytes]

                # チャンクのタイムスタンプ（録音開始からの経過時間）
                timestamp = self._get_current_timestamp()

                try:
                    self.chunk_queue.put_nowait((chunk_with_overlap, timestamp))
                    logger.debug(f"Chunk added to queue: {len(chunk_with_overlap)} bytes at {timestamp:.2f}s")
                except queue.Full:
                    logger.warning("Chunk queue is full, dropping oldest chunk")
                    try:
                        self.chunk_queue.get_nowait()  # 古いチャンクを削除
                        self.chunk_queue.put_nowait((chunk_with_overlap, timestamp))
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

    def _ensure_vad_initialized(self) -> None:
        """VADを初期化（初回のみ）"""
        if self._vad_initialized or not self.vad_enabled:
            return

        self._vad_initialized = True

        try:
            logger.info("Initializing VAD processor...")
            self.vad_processor = VADProcessor(
                sample_rate=self.sample_rate,
                aggressiveness=self.vad_aggressiveness
            )
            logger.info("VAD processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VAD: {e}")
            logger.warning("VAD will be disabled")
            self.vad_enabled = False
            self.vad_processor = None

    def start_processing(self) -> None:
        """チャンク処理スレッドを開始"""
        if self.is_processing:
            logger.warning("Processing already started")
            return

        # VADを初期化（初回のみ）
        self._ensure_vad_initialized()

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

                # VADによる発話検出と発話区間抽出
                processed_chunk = chunk
                should_process = True

                if self.vad_enabled and self.vad_processor:
                    # 発話区間のみを抽出
                    processed_chunk = self.vad_processor.extract_speech_segments(chunk)

                    # 抽出結果が空、または非常に短い（1秒未満）場合はスキップ
                    min_chunk_size = self.sample_rate * 2  # 1秒分（16000Hz * 2bytes * 1sec）
                    if not processed_chunk or len(processed_chunk) < min_chunk_size:
                        chunk_duration = len(processed_chunk) / (self.sample_rate * 2) if processed_chunk else 0
                        logger.info(f"Skipping silent/short chunk at {timestamp:.2f}s (duration: {chunk_duration:.2f}s)")
                        self.total_chunks_skipped += 1
                        should_process = False

                # コールバック関数を呼び出し（発話区間のみを送信）
                if should_process and self.on_chunk_ready:
                    try:
                        self.on_chunk_ready(processed_chunk, timestamp)
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
