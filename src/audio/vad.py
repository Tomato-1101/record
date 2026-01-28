"""
VAD (Voice Activity Detection) モジュール
Silero VAD を使用した音声区間検出
"""
import numpy as np
from typing import Optional
from src.utils.logger import logger

# グローバル変数
_vad_model = None
_vad_utils = None
SILERO_VAD_AVAILABLE = False

# 起動時にVADモデルをロード
try:
    import torch
    import torchaudio
    torch.set_num_threads(1)
    logger.info("Loading Silero VAD model...")
    _vad_model, _vad_utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        onnx=False,
        verbose=False
    )
    SILERO_VAD_AVAILABLE = True
    logger.info("Silero VAD model loaded successfully")
except Exception as e:
    SILERO_VAD_AVAILABLE = False
    logger.error(f"Failed to load Silero VAD: {e}")
    logger.warning("VAD will be disabled. Install with: pip install torch torchaudio")


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
            sample_rate: サンプルレート（8000または16000）
            aggressiveness: VAD感度（0-3: 0=最も寛容, 3=最も厳格）
                          Silero VADではthresholdに変換（0->0.1, 1->0.3, 2->0.5, 3->0.7）
            frame_duration_ms: フレーム長（未使用、互換性のため保持）
        """
        if not SILERO_VAD_AVAILABLE:
            logger.warning("Silero VAD is not available. VAD will be disabled.")
            self.model = None
            return

        # Silero VADは8kまたは16kHzを推奨
        if sample_rate not in [8000, 16000]:
            logger.warning(f"Sample rate {sample_rate}Hz may not be optimal for Silero VAD. Using 16000Hz.")
            sample_rate = 16000

        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness

        # aggressivenessをSilero VADのthresholdに変換
        threshold_map = {0: 0.1, 1: 0.3, 2: 0.5, 3: 0.7}
        self.threshold = threshold_map.get(aggressiveness, 0.5)

        # グローバルのVADモデルを使用
        global _vad_model
        self.model = _vad_model

        logger.info(
            f"VADProcessor initialized: "
            f"sample_rate={sample_rate}Hz, "
            f"threshold={self.threshold} (aggressiveness={aggressiveness})"
        )

    def is_speech(self, audio_data: bytes) -> bool:
        """
        音声データに発話が含まれているか判定

        Args:
            audio_data: 音声データ（bytes）

        Returns:
            発話が含まれている場合True
        """
        if not self.model or not SILERO_VAD_AVAILABLE:
            return True  # VADが利用できない場合は常にTrueを返す

        try:
            global _vad_utils
            get_speech_timestamps = _vad_utils[0]

            # bytes (int16) -> float32 numpy array -> torch tensor
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            import torch
            audio_tensor = torch.from_numpy(audio_float32)

            # Silero VADで発話タイムスタンプを取得
            speech_timestamps = get_speech_timestamps(
                audio_tensor,
                self.model,
                sampling_rate=self.sample_rate,
                threshold=self.threshold,
                min_speech_duration_ms=100,
                min_silence_duration_ms=100
            )

            # 発話区間が存在するかチェック
            return len(speech_timestamps) > 0

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
        if not self.model or not SILERO_VAD_AVAILABLE:
            return 1.0

        try:
            global _vad_utils
            get_speech_timestamps = _vad_utils[0]

            # bytes (int16) -> float32 numpy array -> torch tensor
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            import torch
            audio_tensor = torch.from_numpy(audio_float32)

            # 発話タイムスタンプを取得
            speech_timestamps = get_speech_timestamps(
                audio_tensor,
                self.model,
                sampling_rate=self.sample_rate,
                threshold=self.threshold
            )

            if not speech_timestamps:
                return 0.0

            # 発話区間の合計時間 / 全体の時間
            total_speech_samples = sum(ts['end'] - ts['start'] for ts in speech_timestamps)
            total_samples = len(audio_tensor)

            if total_samples == 0:
                return 1.0

            return total_speech_samples / total_samples

        except Exception as e:
            logger.error(f"VAD confidence error: {e}")
            return 1.0

    def set_aggressiveness(self, aggressiveness: int) -> None:
        """
        VAD感度を設定

        Args:
            aggressiveness: VAD感度（0-3）
        """
        if 0 <= aggressiveness <= 3:
            self.aggressiveness = aggressiveness
            # aggressivenessをthresholdに変換
            threshold_map = {0: 0.1, 1: 0.3, 2: 0.5, 3: 0.7}
            self.threshold = threshold_map.get(aggressiveness, 0.5)

            logger.info(f"VAD threshold set to {self.threshold} (aggressiveness={aggressiveness})")
        else:
            logger.warning(f"Invalid aggressiveness value: {aggressiveness}")

    def is_available(self) -> bool:
        """
        VADが利用可能か確認

        Returns:
            VADが利用可能な場合True
        """
        return SILERO_VAD_AVAILABLE and self.model is not None

    def extract_speech_segments(self, audio_data: bytes) -> bytes:
        """
        音声データから発話区間のみを抽出して結合

        Args:
            audio_data: 音声データ（bytes）

        Returns:
            発話区間のみを結合した音声データ
        """
        if not self.model or not SILERO_VAD_AVAILABLE:
            # VADが利用できない場合は元のデータをそのまま返す
            return audio_data

        try:
            global _vad_utils
            get_speech_timestamps = _vad_utils[0]

            # bytes (int16) -> float32 numpy array -> torch tensor
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            import torch
            audio_tensor = torch.from_numpy(audio_float32)

            # 発話タイムスタンプを取得
            speech_timestamps = get_speech_timestamps(
                audio_tensor,
                self.model,
                sampling_rate=self.sample_rate,
                threshold=self.threshold,
                min_speech_duration_ms=250,  # 最低250ms以上の発話のみ検出
                min_silence_duration_ms=100
            )

            # 早期クリーンアップ
            del audio_tensor
            del audio_float32

            if not speech_timestamps:
                # 発話が全く検出されない場合は空のバイト列を返す
                original_duration = len(audio_data) / (self.sample_rate * 2)
                logger.info(f"VAD: No speech detected in {original_duration:.1f}s chunk")
                return b''

            # 発話区間のみを抽出して結合（memoryviewでゼロコピー）
            audio_view = memoryview(audio_data)
            speech_segments = []
            for ts in speech_timestamps:
                start_sample = ts['start']
                end_sample = ts['end']
                # int16のインデックスに変換
                start_byte = start_sample * 2
                end_byte = end_sample * 2
                speech_segments.append(bytes(audio_view[start_byte:end_byte]))

            extracted_audio = b''.join(speech_segments)

            # ログ出力
            original_duration = len(audio_data) / (self.sample_rate * 2)
            extracted_duration = len(extracted_audio) / (self.sample_rate * 2)
            reduction_ratio = (1 - extracted_duration / original_duration) * 100 if original_duration > 0 else 0

            logger.info(
                f"VAD: {extracted_duration:.1f}s speech extracted from {original_duration:.1f}s chunk "
                f"({reduction_ratio:.1f}% reduced, {len(speech_timestamps)} segments)"
            )

            return extracted_audio

        except Exception as e:
            logger.error(f"VAD extraction error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # エラー時は元のデータを返す
            return audio_data
