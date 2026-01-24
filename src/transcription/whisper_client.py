"""
Groq Whisper API クライアント
Whisper Large V3 Turbo を使用した文字起こし
"""
import io
import time
import wave
from typing import Optional
import httpx
from groq import Groq, AsyncGroq
from src.utils.logger import logger


class WhisperTranscriber:
    """
    Groq Whisper APIクライアント
    - 非同期でAPI呼び出し
    - レート制限対応
    - エラーリトライ
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "whisper-large-v3-turbo",
        language: str = "ja",
        temperature: float = 0.0,
        max_retries: int = 3,
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """
        Whisperクライアントの初期化

        Args:
            api_key: Groq APIキー
            model_name: モデル名
            language: 文字起こし言語
            temperature: 温度パラメータ（0.0-1.0）
            max_retries: 最大リトライ回数
            sample_rate: サンプルレート（Hz）
            channels: チャンネル数
        """
        self.api_key = api_key
        self.model_name = model_name
        self.language = language
        self.temperature = temperature
        self.max_retries = max_retries
        self.sample_rate = sample_rate
        self.channels = channels

        # Groqクライアント
        self.client = Groq(api_key=api_key)
        self.async_client = AsyncGroq(api_key=api_key)

        # 統計情報
        self.total_requests = 0
        self.total_errors = 0

        logger.info(
            f"WhisperTranscriber initialized: "
            f"model={model_name}, language={language}"
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
        try:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(pcm_data)

            # getvalue()はread()よりもメモリ効率的
            return wav_buffer.getvalue()
        finally:
            wav_buffer.close()

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
                audio_file.name = "audio.wav"  # ファイル名が必要

                # Whisper API呼び出し
                response = self.client.audio.transcriptions.create(
                    model=self.model_name,
                    file=audio_file,
                    language=self.language,
                    temperature=self.temperature,
                    response_format="text"
                )

                self.total_requests += 1

                # レスポンスの処理
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

    async def transcribe_async(
        self,
        audio_chunk: bytes,
        timestamp: float = 0.0
    ) -> Optional[str]:
        """
        音声チャンクを文字起こし（非同期）

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

                # Whisper API呼び出し（非同期）
                response = await self.async_client.audio.transcriptions.create(
                    model=self.model_name,
                    file=audio_file,
                    language=self.language,
                    temperature=self.temperature,
                    response_format="text"
                )

                self.total_requests += 1

                # レスポンスの処理
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
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Rate limit exceeded, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
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
                await asyncio.sleep(1)

        return None

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
