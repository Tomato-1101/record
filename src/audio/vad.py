"""
VAD (Voice Activity Detection) モジュール
webrtcvad を使用した音声区間検出
"""
try:
    import webrtcvad
    WEBRTC_VAD_AVAILABLE = True
except ImportError:
    WEBRTC_VAD_AVAILABLE = False
    webrtcvad = None

import numpy as np
from typing import Optional
from src.utils.logger import logger


class VADProcessor:
    """
    VAD処理クラス
    音声区間の検出と無音区間のフィルタリング
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 2,
        frame_duration_ms: int = 30
    ):
        """
        VADプロセッサの初期化

        Args:
            sample_rate: サンプルレート（8000, 16000, 32000, 48000のいずれか）
            aggressiveness: VAD感度（0-3: 0=最も寛容, 3=最も厳格）
            frame_duration_ms: フレーム長（10, 20, 30のいずれか）
        """
        if not WEBRTC_VAD_AVAILABLE:
            logger.warning("webrtcvad is not installed. VAD will be disabled.")
            self.vad = None
            return

        # webrtcvadは8k, 16k, 32k, 48kHzのみサポート
        if sample_rate not in [8000, 16000, 32000, 48000]:
            logger.warning(f"Invalid sample rate {sample_rate} for webrtcvad. Using 16000Hz.")
            sample_rate = 16000

        # フレーム長は10, 20, 30msのみサポート
        if frame_duration_ms not in [10, 20, 30]:
            logger.warning(f"Invalid frame duration {frame_duration_ms}ms. Using 30ms.")
            frame_duration_ms = 30

        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = frame_duration_ms

        # フレームサイズ（バイト数）
        self.frame_size = int(sample_rate * frame_duration_ms / 1000 * 2)  # 16-bit = 2 bytes

        # VADインスタンス
        self.vad = webrtcvad.Vad(aggressiveness)

        logger.info(
            f"VADProcessor initialized: "
            f"sample_rate={sample_rate}Hz, "
            f"aggressiveness={aggressiveness}, "
            f"frame_duration={frame_duration_ms}ms"
        )

    def is_speech(self, audio_data: bytes) -> bool:
        """
        音声データに発話が含まれているか判定

        Args:
            audio_data: 音声データ（bytes）

        Returns:
            発話が含まれている場合True
        """
        if not self.vad or not WEBRTC_VAD_AVAILABLE:
            # VADが利用できない場合は常にTrueを返す
            return True

        try:
            # 音声データをフレームに分割して判定
            num_frames = len(audio_data) // self.frame_size
            speech_frames = 0
            total_frames = 0

            for i in range(num_frames):
                start = i * self.frame_size
                end = start + self.frame_size
                frame = audio_data[start:end]

                if len(frame) == self.frame_size:
                    try:
                        if self.vad.is_speech(frame, self.sample_rate):
                            speech_frames += 1
                        total_frames += 1
                    except Exception as e:
                        logger.debug(f"VAD frame error: {e}")
                        continue

            # 30%以上のフレームで発話が検出された場合、発話ありと判定
            if total_frames == 0:
                return True  # フレームがない場合は念のため処理する

            speech_ratio = speech_frames / total_frames
            return speech_ratio > 0.3

        except Exception as e:
            logger.error(f"VAD error: {e}")
            return True  # エラー時は念のため処理する

    def get_speech_confidence(self, audio_data: bytes) -> float:
        """
        音声データの発話信頼度を取得（0.0-1.0）

        Args:
            audio_data: 音声データ（bytes）

        Returns:
            発話信頼度（0.0=無音, 1.0=確実に発話）
        """
        if not self.vad or not WEBRTC_VAD_AVAILABLE:
            return 1.0

        try:
            num_frames = len(audio_data) // self.frame_size
            speech_frames = 0
            total_frames = 0

            for i in range(num_frames):
                start = i * self.frame_size
                end = start + self.frame_size
                frame = audio_data[start:end]

                if len(frame) == self.frame_size:
                    try:
                        if self.vad.is_speech(frame, self.sample_rate):
                            speech_frames += 1
                        total_frames += 1
                    except Exception:
                        continue

            if total_frames == 0:
                return 1.0

            return speech_frames / total_frames

        except Exception as e:
            logger.error(f"VAD confidence error: {e}")
            return 1.0

    def set_aggressiveness(self, aggressiveness: int) -> None:
        """
        VAD感度を設定

        Args:
            aggressiveness: VAD感度（0-3）
        """
        if not self.vad or not WEBRTC_VAD_AVAILABLE:
            return

        if 0 <= aggressiveness <= 3:
            self.aggressiveness = aggressiveness
            self.vad.set_mode(aggressiveness)
            logger.info(f"VAD aggressiveness set to {aggressiveness}")
        else:
            logger.warning(f"Invalid aggressiveness value: {aggressiveness}")

    def is_available(self) -> bool:
        """
        VADが利用可能か確認

        Returns:
            VADが利用可能な場合True
        """
        return WEBRTC_VAD_AVAILABLE and self.vad is not None
