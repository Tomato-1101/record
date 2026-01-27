"""
VAD (Voice Activity Detection) モジュール
Silero VAD を使用した音声区間検出
"""
try:
    import torch
    import torchaudio
    torch.set_num_threads(1)
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False, onnx=False)
    (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
    SILERO_VAD_AVAILABLE = True
    print("[VAD] Silero VAD successfully loaded")
except Exception as e:
    SILERO_VAD_AVAILABLE = False
    model = None
    utils = None
    VADIterator = None
    print(f"[VAD] ERROR: Silero VAD not available: {e}")
    print("[VAD] Install with: pip install silero-vad torch torchaudio")

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
            sample_rate: サンプルレート（8000または16000）
            aggressiveness: VAD感度（0-3: 0=最も寛容, 3=最も厳格）
                          Silero VADではthresholdに変換（0->0.1, 1->0.3, 2->0.5, 3->0.7）
            frame_duration_ms: フレーム長（未使用、互換性のため保持）
        """
        if not SILERO_VAD_AVAILABLE:
            logger.warning("Silero VAD is not installed. VAD will be disabled.")
            self.model = None
            self.vad_iterator = None
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

        # Silero VADモデルとイテレータ
        self.model = model
        self.vad_iterator = VADIterator(
            model,
            threshold=self.threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=100,
            speech_pad_ms=30
        )

        # ストリーミングVAD用の状態管理
        self.is_speaking = False
        self.silence_frames = 0
        self.speech_frames = 0

        logger.info(
            f"VADProcessor initialized with Silero VAD: "
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
            # VADが利用できない場合は常にTrueを返す
            return True

        try:
            # bytes (int16) -> float32 numpy array -> torch tensor
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0  # normalize to [-1, 1]
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
            # bytes (int16) -> float32 numpy array -> torch tensor
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
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
        if not self.model or not SILERO_VAD_AVAILABLE:
            return

        if 0 <= aggressiveness <= 3:
            self.aggressiveness = aggressiveness
            # aggressivenessをthresholdに変換
            threshold_map = {0: 0.1, 1: 0.3, 2: 0.5, 3: 0.7}
            self.threshold = threshold_map.get(aggressiveness, 0.5)

            # VADイテレータを再作成
            self.vad_iterator = VADIterator(
                self.model,
                threshold=self.threshold,
                sampling_rate=self.sample_rate,
                min_silence_duration_ms=100,
                speech_pad_ms=30
            )

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

    def process_frame(self, audio_frame: bytes, silence_threshold_ms: int = 500) -> str:
        """
        リアルタイムで音声フレームを処理し、発話状態を返す

        Args:
            audio_frame: 音声データ（bytes）
            silence_threshold_ms: 無音閾値（ミリ秒）

        Returns:
            "speech" | "silence" | "speech_end"
        """
        if not self.model or not SILERO_VAD_AVAILABLE or not self.vad_iterator:
            # VADが利用できない場合は常に発話中として扱う
            return "speech"

        try:
            # bytes (int16) -> float32 numpy array -> torch tensor
            audio_int16 = np.frombuffer(audio_frame, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio_float32)

            # VADIteratorでフレームを処理
            speech_dict = self.vad_iterator(audio_tensor, return_seconds=False)

            # speech_dictが空でない = 発話区間が検出された
            if speech_dict:
                self.is_speaking = True
                self.silence_frames = 0
                self.speech_frames += 1
                return "speech"
            else:
                # 無音フレーム
                self.silence_frames += 1

                # フレーム長を計算（ミリ秒）
                frame_duration_ms = len(audio_frame) / (self.sample_rate * 2) * 1000

                # 無音が閾値を超えた場合
                if self.is_speaking and (self.silence_frames * frame_duration_ms >= silence_threshold_ms):
                    self.is_speaking = False
                    self.speech_frames = 0
                    return "speech_end"

                return "silence"

        except Exception as e:
            logger.error(f"VAD process_frame error: {e}")
            return "speech"  # エラー時は発話中として扱う

    def reset_state(self) -> None:
        """VAD状態をリセット"""
        if self.vad_iterator and SILERO_VAD_AVAILABLE:
            # VADIteratorを再作成してリセット
            self.vad_iterator = VADIterator(
                self.model,
                threshold=self.threshold,
                sampling_rate=self.sample_rate,
                min_silence_duration_ms=100,
                speech_pad_ms=30
            )
        self.is_speaking = False
        self.silence_frames = 0
        self.speech_frames = 0

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
            # bytes (int16) -> float32 numpy array -> torch tensor
            # frombufferはゼロコピー（読み取り専用ビュー）
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            # 正規化（コピーは避けられないが、明示的にメモリ管理）
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            # torch.from_numpyはゼロコピー（メモリ共有）
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
            original_duration = len(audio_data) / (self.sample_rate * 2)  # 16-bit = 2 bytes
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
