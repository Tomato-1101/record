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
        channels: int = 1,
        prompt_template: str = "",
        use_context: bool = False
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
            prompt_template: プロンプトテンプレート
            use_context: 前チャンクをコンテキストとして使用
        """
        self.api_key = api_key
        self.model_name = model_name
        # 言語コードを正規化（zh-CN → zh）
        self.language = self._normalize_language_code(language)
        self.enable_diarization = enable_diarization
        self.max_retries = max_retries
        self.sample_rate = sample_rate
        self.channels = channels
        self.prompt_template = prompt_template
        self.use_context = use_context
        self.previous_text = ""
        self.previous_speakers = []  # 最後の3話者を追跡

        # OpenAIクライアント
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)

        # 統計情報
        self.total_requests = 0
        self.total_errors = 0

        logger.info(
            f"GPT4oTranscriber initialized: "
            f"model={model_name}, language={self.language}, diarization={enable_diarization}"
        )

    def _normalize_language_code(self, language: str) -> str:
        """
        言語コードを正規化

        Args:
            language: 言語コード（例: zh-CN, zh, ja）

        Returns:
            正規化された言語コード
        """
        # zh-CN を zh に変換（APIの互換性のため）
        if language.startswith("zh"):
            return "zh"
        return language

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
                audio_file.name = "audio.wav"

                # プロンプト構築
                prompt = self.prompt_template if self.prompt_template else ""
                if self.use_context and self.previous_text:
                    context = self.previous_text[-50:]  # 最後の50文字
                    prompt = f"{prompt}\n前の発話: {context}" if prompt else f"前の発話: {context}"

                # API呼び出しパラメータ
                params = {
                    "model": self.model_name,
                    "file": audio_file,
                }

                # プロンプトを追加
                if prompt:
                    params["prompt"] = prompt

                # 話者分離が有効な場合はdiarized_jsonを使用
                if self.enable_diarization:
                    params["response_format"] = "diarized_json"
                else:
                    params["response_format"] = "text"

                # GPT-4o Audio API呼び出し
                response = self.client.audio.transcriptions.create(**params)

                self.total_requests += 1

                # レスポンスの処理
                if self.enable_diarization:
                    # diarized_jsonレスポンスを処理
                    logger.debug(f"Diarize response type: {type(response)}")
                    text = self._format_diarized_response(response, timestamp)
                else:
                    # 通常のテキストレスポンス
                    if isinstance(response, str):
                        text = response.strip()
                    else:
                        text = response.text.strip() if hasattr(response, "text") else ""

                if text:
                    # 前チャンクとして保存
                    self.previous_text = text
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
            response: APIレスポンス（diarized_json形式）
            base_timestamp: 基準タイムスタンプ（秒）

        Returns:
            フォーマット済みテキスト（話者A: テキスト形式）
        """
        try:
            # レスポンスがオブジェクトの場合、辞書に変換
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            elif hasattr(response, 'to_dict'):
                response_dict = response.to_dict()
            elif isinstance(response, dict):
                response_dict = response
            else:
                # レスポンスがオブジェクトの場合、属性でアクセス
                response_dict = {}
                if hasattr(response, 'segments'):
                    response_dict['segments'] = response.segments
                if hasattr(response, 'text'):
                    response_dict['text'] = response.text

            logger.debug(f"Response keys: {list(response_dict.keys())}")

            # セグメント情報を取得
            segments = response_dict.get("segments", [])

            # セグメントをマージ
            if segments:
                segments = self._merge_speaker_segments(segments)

            if not segments:
                # セグメントがない場合、全体のテキストを返す
                text = response_dict.get("text", "")
                if text:
                    return text.strip()
                # 属性でアクセスを試みる
                if hasattr(response, 'text'):
                    return response.text.strip()
                return ""

            # 話者ラベルのマッピング
            speaker_map = {}
            speaker_labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

            formatted_parts = []
            for segment in segments:
                # セグメントが辞書でない場合、オブジェクトとして扱う
                if isinstance(segment, dict):
                    speaker_id = segment.get("speaker", "UNKNOWN")
                    text = segment.get("text", "").strip()
                else:
                    speaker_id = getattr(segment, "speaker", "UNKNOWN")
                    text = getattr(segment, "text", "").strip()

                if not text:
                    continue

                # 話者ラベルの取得または生成
                if speaker_id not in speaker_map:
                    speaker_index = len(speaker_map)
                    if speaker_index < len(speaker_labels):
                        speaker_map[speaker_id] = f"話者{speaker_labels[speaker_index]}"
                    else:
                        speaker_map[speaker_id] = f"話者{speaker_index + 1}"

                speaker_label = speaker_map[speaker_id]

                # フォーマット: 話者A: テキスト
                formatted_parts.append(f"{speaker_label}: {text}")

            # 話者情報を保存（最後の3話者）
            if segments:
                speakers = []
                for segment in segments:
                    if isinstance(segment, dict):
                        speaker_id = segment.get("speaker")
                    else:
                        speaker_id = getattr(segment, "speaker", None)
                    if speaker_id:
                        speakers.append(speaker_id)

                # 最後の3話者を保存
                self.previous_speakers.extend(speakers[-3:])
                if len(self.previous_speakers) > 3:
                    self.previous_speakers = self.previous_speakers[-3:]

            if formatted_parts:
                return " ".join(formatted_parts)
            else:
                # セグメントはあるがテキストが空の場合
                return ""

        except Exception as e:
            logger.error(f"Error formatting diarized response: {e}")
            logger.debug(f"Response type: {type(response)}")
            logger.debug(f"Response: {response}")
            # エラー時は通常のテキストとして処理を試みる
            try:
                if hasattr(response, 'text'):
                    return response.text.strip()
                elif isinstance(response, dict) and 'text' in response:
                    return response['text'].strip()
            except:
                pass
            return ""

    def _merge_speaker_segments(self, segments: list) -> list:
        """
        隣接する同一話者のセグメントをマージ

        Args:
            segments: セグメントリスト

        Returns:
            マージ済みセグメントリスト
        """
        if not segments:
            return segments

        merged = []
        current_segment = None

        # 最初のセグメントを辞書形式に変換
        first_seg = segments[0]
        if isinstance(first_seg, dict):
            current_segment = first_seg.copy()
        else:
            current_segment = {
                "speaker": getattr(first_seg, "speaker", "UNKNOWN"),
                "start": getattr(first_seg, "start", 0),
                "end": getattr(first_seg, "end", 0),
                "text": getattr(first_seg, "text", "")
            }

        for next_seg in segments[1:]:
            # 次のセグメントを辞書形式に変換
            if isinstance(next_seg, dict):
                next_segment = next_seg
            else:
                next_segment = {
                    "speaker": getattr(next_seg, "speaker", "UNKNOWN"),
                    "start": getattr(next_seg, "start", 0),
                    "end": getattr(next_seg, "end", 0),
                    "text": getattr(next_seg, "text", "")
                }

            # 同じ話者で2秒以内の間隔?
            time_gap = next_segment.get("start", 0) - current_segment.get("end", 0)

            if (next_segment.get("speaker") == current_segment.get("speaker") and
                time_gap < 2.0):
                # マージ
                current_segment["end"] = next_segment.get("end", current_segment["end"])
                current_segment["text"] += " " + next_segment.get("text", "")
            else:
                # 現在のセグメントを保存し、新しいセグメントを開始
                merged.append(current_segment)
                current_segment = next_segment.copy()

        merged.append(current_segment)
        return merged

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
