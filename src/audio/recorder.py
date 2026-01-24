"""
音声録音モジュール
PyAudioを使用した連続録音処理
"""
import threading
import time
from typing import Optional, Callable
import pyaudio
import numpy as np
from src.utils.logger import logger
from src.audio.buffer import AudioBufferManager


class AudioRecorder:
    """
    連続録音を担当するクラス
    - 別スレッドで常時録音を継続
    - 指定間隔でチャンクをBufferManagerに送出
    - 録音停止まで中断なし
    """

    # PyAudio フォーマット定数
    FORMAT_MAP = {
        "paInt16": pyaudio.paInt16,
        "paInt32": pyaudio.paInt32,
        "paFloat32": pyaudio.paFloat32,
    }

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        format_str: str = "paInt16",
        buffer_manager: Optional[AudioBufferManager] = None,
        device_index: Optional[int] = None
    ):
        """
        録音クラスの初期化

        Args:
            sample_rate: サンプルレート（Hz）
            channels: チャンネル数（1=モノラル、2=ステレオ）
            chunk_size: PyAudioバッファサイズ
            format_str: 音声フォーマット（"paInt16" | "paInt32" | "paFloat32"）
            buffer_manager: バッファマネージャ
            device_index: 入力デバイスインデックス（Noneの場合はデフォルト）
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.format = self.FORMAT_MAP.get(format_str, pyaudio.paInt16)
        self.device_index = device_index

        # PyAudioインスタンス
        self.pyaudio = pyaudio.PyAudio()

        # バッファマネージャ
        self.buffer_manager = buffer_manager

        # 録音制御
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None
        self.stream: Optional[pyaudio.Stream] = None

        # 統計情報
        self.total_frames_recorded = 0
        self.start_time: Optional[float] = None

        logger.info(
            f"AudioRecorder initialized: "
            f"sample_rate={sample_rate}Hz, "
            f"channels={channels}, "
            f"chunk_size={chunk_size}, "
            f"format={format_str}"
        )

        # 利用可能なデバイスをログに出力
        self._log_available_devices()

    def list_devices(self) -> list:
        """
        利用可能な音声デバイス一覧を取得

        Returns:
            デバイス情報のリスト
        """
        devices = []
        for i in range(self.pyaudio.get_device_count()):
            device_info = self.pyaudio.get_device_info_by_index(i)
            if device_info["maxInputChannels"] > 0:  # 入力デバイスのみ
                devices.append({
                    "index": i,
                    "name": device_info["name"],
                    "channels": device_info["maxInputChannels"],
                    "sample_rate": int(device_info["defaultSampleRate"])
                })
        return devices

    def _log_available_devices(self) -> None:
        """利用可能なデバイスをログに出力"""
        try:
            logger.info("=== Available Input Devices ===")

            # デフォルトデバイス情報
            try:
                default_info = self.pyaudio.get_default_input_device_info()
                logger.info(f"Default Input Device: {default_info['name']} (index: {default_info['index']})")
            except Exception as e:
                logger.warning(f"No default input device found: {e}")

            # すべての入力デバイス
            devices = self.list_devices()
            if devices:
                for dev in devices:
                    logger.info(f"  [{dev['index']}] {dev['name']} - {dev['channels']}ch, {dev['sample_rate']}Hz")
            else:
                logger.warning("No input devices found!")

            logger.info("=" * 35)
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")

    def start_recording(self) -> None:
        """録音を開始"""
        if self.is_recording:
            logger.warning("Recording already started")
            return

        try:
            # デバイスインデックスの決定
            device_index = self.device_index
            if device_index is None:
                # デフォルトデバイスを明示的に取得
                try:
                    default_device = self.pyaudio.get_default_input_device_info()
                    device_index = default_device['index']
                    logger.info(f"Using default input device: {default_device['name']} (index: {device_index})")
                except Exception as e:
                    logger.error(f"Failed to get default input device: {e}")
                    # device_indexをNoneのままにして、PyAudioに任せる
                    device_index = None

            # PyAudioストリームを開く
            self.stream = self.pyaudio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=device_index,
                stream_callback=None  # コールバックは使わず、スレッドで処理
            )

            # 録音状態を設定
            self.is_recording = True
            self.total_frames_recorded = 0
            self.start_time = time.time()

            # バッファマネージャの処理を開始
            if self.buffer_manager:
                self.buffer_manager.start_processing()

            # 録音スレッドを開始
            self.recording_thread = threading.Thread(
                target=self._recording_loop,
                daemon=True
            )
            self.recording_thread.start()

            logger.info("Recording started")

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.is_recording = False
            raise

    def stop_recording(self) -> None:
        """録音を停止"""
        if not self.is_recording:
            logger.warning("Recording not started")
            return

        self.is_recording = False

        # 録音スレッドの終了を待機
        if self.recording_thread:
            self.recording_thread.join(timeout=5.0)

        # ストリームを閉じる
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # バッファマネージャの処理を停止
        if self.buffer_manager:
            self.buffer_manager.stop_processing()

        elapsed_time = time.time() - self.start_time if self.start_time else 0
        logger.info(
            f"Recording stopped: "
            f"total_frames={self.total_frames_recorded}, "
            f"elapsed_time={elapsed_time:.2f}s"
        )

    def _recording_loop(self) -> None:
        """録音ループ（スレッドで実行）"""
        while self.is_recording:
            try:
                # PyAudioストリームから音声データを読み込み
                audio_data = self.stream.read(
                    self.chunk_size,
                    exception_on_overflow=False
                )

                self.total_frames_recorded += self.chunk_size

                # バッファマネージャに音声データを追加
                if self.buffer_manager:
                    self.buffer_manager.add_audio_data(audio_data)

            except Exception as e:
                logger.error(f"Error in recording loop: {e}")
                if not self.is_recording:
                    break
                time.sleep(0.1)  # エラー時は少し待機

    def get_elapsed_time(self) -> float:
        """
        録音開始からの経過時間を取得

        Returns:
            経過時間（秒）
        """
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    def get_stats(self) -> dict:
        """
        統計情報を取得

        Returns:
            統計情報の辞書
        """
        return {
            "is_recording": self.is_recording,
            "total_frames_recorded": self.total_frames_recorded,
            "elapsed_time_sec": self.get_elapsed_time(),
            "buffer_stats": self.buffer_manager.get_stats() if self.buffer_manager else {}
        }

    def close(self) -> None:
        """録音を停止してストリームを閉じる（PyAudioは終了しない）"""
        if self.is_recording:
            self.stop_recording()
        logger.info("AudioRecorder closed")

    def cleanup(self) -> None:
        """リソースのクリーンアップ（PyAudioを終了）"""
        if self.is_recording:
            self.stop_recording()

        if self.pyaudio:
            self.pyaudio.terminate()
            self.pyaudio = None
            logger.info("AudioRecorder cleaned up")

    def __del__(self):
        """デストラクタ"""
        try:
            if self.pyaudio:
                self.cleanup()
        except:
            pass
