"""
OpenAI GPT-4o Audio API クライアント
gpt-4o-transcribe および gpt-4o-transcribe-diarize 対応
"""
import io
import time
import wave
from typing import Optional, List, Dict
import httpx
from openai import OpenAI, AsyncOpenAI
from src.utils.logger import logger


class GPT4oTranscriber:
    """
    OpenAI GPT-4o Audio APIクライアント
    - gpt-4o-transcribe: 高精度文字起こし
    - gpt-4o-transcribe-diarize: 話者分離付き文字起こし
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-transcribe",
        language: str = "ja",
        enable_diarization: bool = False,
        max_retries: int = 3,
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """
        GPT-4o クライアントの初期化

        Args:
            api_key: OpenAI APIキー
            model_name: モデル名（gpt-4o-transcribe | gpt-4o-transcribe-diarize）
            language: 文字起こし言語
            enable_diarization: 話者分離を有効化
            max_retries: 最大リトライ回数
            sample_rate: サンプルレート（Hz）
            channels: チャンネル数
        """
        self.api_key = api_key
        self.model_name = model_name
        self.language = language
        self.enable_diarization = enable_diarization
        self.max_retries = max_retries
        self.sample_rate = sample_rate
        self.channels = channels

        # OpenAIクライアント
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)

        # 統計情報
        self.total_requests = 0
        self.total_errors = 0

        logger.info(
            f"GPT4oTranscriber initialized: "
            f"model={model_name}, diarization={enable_diarization}"
        )

    def _convert_to_wav(self, pcm_data: bytes) -> bytes:
        """
        生のPCMデータをWAVフォーマットに変換

        Args:
            pcm_data: 生のPCMデータ（bytes）

        Returns:
            WAVフォーマットの音声データ
        """
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_data)

        wav_buffer.seek(0)
        return wav_buffer.read()

    def transcribe(
        self,
        audio_chunk: bytes,
        timestamp: float = 0.0
    ) -> Optional[str]:
        """
        音声チャンクを文字起こし（同期）

        Args:
            audio_chunk: 音声データ（bytes）
            timestamp: タイムスタンプ（秒）

        Returns:
            文字起こし結果のテキスト
        """
        for attempt in range(self.max_retries):
            try:
                # PCMデータをWAVフォーマットに変換
                wav_data = self._convert_to_wav(audio_chunk)

                # 音声データをファイルライクオブジェクトに変換
                audio_file = io.BytesIO(wav_data)
                audio_file.name = "audio.wav"

                # API呼び出しパラメータ
                params = {
                    "model": self.model_name,
                    "file": audio_file,
                }

                # 話者分離が有効な場合
                if self.enable_diarization:
                    params["response_format"] = "diarized_json"
                    params["chunking_strategy"] = "auto"
                else:
                    params["response_format"] = "text"

                # GPT-4o Audio API呼び出し
                response = self.client.audio.transcriptions.create(**params)

                self.total_requests += 1

                # レスポンスの処理
                if self.enable_diarization:
                    # 話者分離付きレスポンス
                    text = self._format_diarized_response(response, timestamp)
                else:
                    # 通常のテキストレスポンス
                    if isinstance(response, str):
                        text = response.strip()
                    else:
                        text = response.text.strip() if hasattr(response, "text") else ""

                if text:
                    logger.info(
                        f"Transcription success: {len(text)} chars at {timestamp:.2f}s"
                    )
                    return text
                else:
                    logger.warning(f"Empty transcription at {timestamp:.2f}s")
                    return None

            except httpx.HTTPStatusError as e:
                self.total_errors += 1
                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # 指数バックオフ
                    logger.warning(
                        f"Rate limit exceeded, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP error {e.response.status_code}: {e}")
                    if attempt == self.max_retries - 1:
                        return None

            except Exception as e:
                self.total_errors += 1
                logger.error(
                    f"Transcription error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(1)

        return None

    def _format_diarized_response(
        self,
        response: any,
        base_timestamp: float
    ) -> str:
        """
        話者分離レスポンスをフォーマット

        Args:
            response: APIレスポンス
            base_timestamp: 基準タイムスタンプ（秒）

        Returns:
            フォーマット済みテキスト
        """
        try:
            segments = response.get("segments", []) if isinstance(response, dict) else []

            if not segments:
                return ""

            # 話者ラベルのマッピング（SPEAKER_0 -> 話者A, SPEAKER_1 -> 話者B, ...）
            speaker_map = {}
            speaker_labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

            formatted_lines = []
            for segment in segments:
                speaker_id = segment.get("speaker", "UNKNOWN")
                start_time = segment.get("start", 0.0)
                text = segment.get("text", "").strip()

                if not text:
                    continue

                # 話者ラベルの取得または生成
                if speaker_id not in speaker_map:
                    speaker_index = len(speaker_map)
                    speaker_map[speaker_id] = f"話者{speaker_labels[speaker_index]}"

                speaker_label = speaker_map[speaker_id]

                # タイムスタンプの計算（基準タイムスタンプ + セグメント開始時刻）
                absolute_time = base_timestamp + start_time
                time_str = self._format_timestamp(absolute_time)

                # フォーマット: [00:00:00] [話者A] テキスト
                formatted_lines.append(f"[{time_str}] [{speaker_label}] {text}")

            return "\n".join(formatted_lines)

        except Exception as e:
            logger.error(f"Error formatting diarized response: {e}")
            return ""

    def _format_timestamp(self, seconds: float) -> str:
        """
        秒数をタイムスタンプ文字列に変換

        Args:
            seconds: 秒数

        Returns:
            タイムスタンプ文字列（HH:MM:SS形式）
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def get_stats(self) -> dict:
        """
        統計情報を取得

        Returns:
            統計情報の辞書
        """
        return {
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "success_rate": (
                (self.total_requests - self.total_errors) / self.total_requests * 100
                if self.total_requests > 0 else 0
            )
        }
