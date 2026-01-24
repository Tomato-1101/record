"""
メインウィンドウGUI
customtkinterを使用したモダンなUI
"""
import os
import datetime
from pathlib import Path
from typing import Optional
import customtkinter as ctk
import pyperclip
from src.utils.logger import logger
from src.config.settings import Settings
from src.audio.recorder import AudioRecorder
from src.audio.buffer import AudioBufferManager
from src.transcription.whisper_client import WhisperTranscriber
from src.transcription.gpt4o_client import GPT4oTranscriber


class MainWindow(ctk.CTk):
    """メインウィンドウクラス"""

    def __init__(self, settings: Settings):
        super().__init__()

        self.settings = settings
        self.recorder: Optional[AudioRecorder] = None
        self.buffer_manager: Optional[AudioBufferManager] = None
        self.transcriber: Optional[any] = None

        # 文字起こしテキスト
        self.transcript_text = ""
        self.output_file_path: Optional[str] = None

        # UIのセットアップ
        self._setup_ui()
        self._setup_recorder()

        logger.info("MainWindow initialized")

    def _setup_ui(self) -> None:
        """UIのセットアップ"""
        # ウィンドウ設定
        self.title("議事録文字起こし")
        self.geometry("900x700")

        # テーマ設定
        theme = self.settings.get("ui.theme", "dark")
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")

        # グリッド設定
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトルバー
        self._create_title_bar()

        # テキスト表示エリア
        self._create_text_area()

        # ステータスバー
        self._create_status_bar()

        # コントロールパネル
        self._create_control_panel()

    def _create_title_bar(self) -> None:
        """タイトルバーの作成"""
        title_frame = ctk.CTkFrame(self, height=50)
        title_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        title_frame.grid_propagate(False)

        title_label = ctk.CTkLabel(
            title_frame,
            text="📝 議事録文字起こし",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(side="left", padx=20, pady=10)

    def _create_text_area(self) -> None:
        """テキスト表示エリアの作成"""
        text_frame = ctk.CTkFrame(self)
        text_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self.text_box = ctk.CTkTextbox(
            text_frame,
            font=ctk.CTkFont(size=14),
            wrap="word"
        )
        self.text_box.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    def _create_status_bar(self) -> None:
        """ステータスバーの作成"""
        status_frame = ctk.CTkFrame(self, height=40)
        status_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        status_frame.grid_propagate(False)

        # 録音時間
        self.time_label = ctk.CTkLabel(
            status_frame,
            text="録音時間: 00:00:00",
            font=ctk.CTkFont(size=12)
        )
        self.time_label.pack(side="left", padx=20)

        # 状態
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="状態: 待機中",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=20)

    def _create_control_panel(self) -> None:
        """コントロールパネルの作成"""
        control_frame = ctk.CTkFrame(self, height=80)
        control_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        control_frame.grid_propagate(False)

        # 録音開始ボタン
        self.start_button = ctk.CTkButton(
            control_frame,
            text="🎙️ 録音開始",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=150,
            height=50,
            command=self._start_recording
        )
        self.start_button.pack(side="left", padx=10, pady=15)

        # 停止ボタン
        self.stop_button = ctk.CTkButton(
            control_frame,
            text="⏹️ 停止",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=150,
            height=50,
            command=self._stop_recording,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=10, pady=15)

        # コピーボタン
        self.copy_button = ctk.CTkButton(
            control_frame,
            text="📋 コピー",
            font=ctk.CTkFont(size=14),
            width=120,
            height=50,
            command=self._copy_to_clipboard
        )
        self.copy_button.pack(side="left", padx=10, pady=15)

        # 設定ボタン
        self.settings_button = ctk.CTkButton(
            control_frame,
            text="⚙️ 設定",
            font=ctk.CTkFont(size=14),
            width=120,
            height=50,
            command=self._open_settings
        )
        self.settings_button.pack(side="left", padx=10, pady=15)

    def _setup_recorder(self) -> None:
        """録音システムのセットアップ"""
        # バッファマネージャの作成
        chunk_duration = self.settings.get("transcription.chunk_duration_sec", 30)
        sample_rate = self.settings.get("audio.sample_rate", 16000)

        self.buffer_manager = AudioBufferManager(
            chunk_duration_sec=chunk_duration,
            sample_rate=sample_rate,
            channels=1,
            on_chunk_ready=self._on_chunk_ready
        )

        # 録音デバイスの作成
        self.recorder = AudioRecorder(
            sample_rate=sample_rate,
            channels=1,
            chunk_size=self.settings.get("audio.chunk_size", 1024),
            format_str=self.settings.get("audio.format", "paInt16"),
            buffer_manager=self.buffer_manager
        )

        # 文字起こしクライアントの作成
        self._setup_transcriber()

    def _setup_transcriber(self) -> None:
        """文字起こしクライアントのセットアップ"""
        model = self.settings.get("transcription.model", "whisper-groq")
        language = self.settings.get("transcription.language", "ja")

        if model == "whisper-groq":
            if not self.settings.groq_api_key:
                logger.error("Groq API key not found")
                return

            self.transcriber = WhisperTranscriber(
                api_key=self.settings.groq_api_key,
                model_name=self.settings.get("transcription.whisper.model_name",
                                            "whisper-large-v3-turbo"),
                language=language,
                temperature=self.settings.get("transcription.whisper.temperature", 0.0)
            )

        elif model in ["gpt-4o-transcribe", "gpt-4o-diarize"]:
            if not self.settings.openai_api_key:
                logger.error("OpenAI API key not found")
                return

            enable_diarization = (model == "gpt-4o-diarize")
            model_name = "gpt-4o-transcribe-diarize" if enable_diarization else "gpt-4o-transcribe"

            self.transcriber = GPT4oTranscriber(
                api_key=self.settings.openai_api_key,
                model_name=model_name,
                language=language,
                enable_diarization=enable_diarization
            )

    def _on_chunk_ready(self, audio_chunk: bytes, timestamp: float) -> None:
        """
        チャンク準備完了時のコールバック

        Args:
            audio_chunk: 音声データ
            timestamp: タイムスタンプ
        """
        if not self.transcriber:
            logger.warning("Transcriber not initialized")
            return

        # 文字起こし実行
        text = self.transcriber.transcribe(audio_chunk, timestamp)

        if text:
            # タイムスタンプ付きでテキストを追加
            time_str = self._format_timestamp(timestamp)
            formatted_text = f"[{time_str}] {text}\n"

            self.transcript_text += formatted_text

            # UIを更新（メインスレッドで実行）
            self.after(0, self._update_text_display, formatted_text)

            # ファイルに自動保存
            if self.settings.get("output.auto_save", True):
                self._save_to_file()

    def _format_timestamp(self, seconds: float) -> str:
        """タイムスタンプをフォーマット"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _update_text_display(self, text: str) -> None:
        """テキスト表示を更新"""
        self.text_box.insert("end", text)
        self.text_box.see("end")  # 自動スクロール

    def _start_recording(self) -> None:
        """録音開始"""
        try:
            # 出力ファイルの準備
            self._prepare_output_file()

            # 録音開始
            self.recorder.start_recording()

            # UIの更新
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.status_label.configure(text="状態: ● 録音中")

            # タイマー開始
            self._update_timer()

            logger.info("Recording started")

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.status_label.configure(text=f"エラー: {e}")

    def _stop_recording(self) -> None:
        """録音停止"""
        try:
            # 録音停止
            self.recorder.stop_recording()

            # UIの更新
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_label.configure(text="状態: 待機中")

            logger.info("Recording stopped")

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")

    def _update_timer(self) -> None:
        """タイマー更新"""
        if self.recorder and self.recorder.is_recording:
            elapsed = self.recorder.get_elapsed_time()
            time_str = self._format_timestamp(elapsed)
            self.time_label.configure(text=f"録音時間: {time_str}")

            # 1秒後に再度更新
            self.after(1000, self._update_timer)

    def _prepare_output_file(self) -> None:
        """出力ファイルの準備"""
        output_dir = Path(self.settings.get("output.directory", "output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        # ファイル名: transcript_YYYYMMDD_HHMMSS.txt
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = self.settings.get("output.file_prefix", "transcript_")
        format_ext = self.settings.get("output.format", "txt")

        filename = f"{prefix}{timestamp}.{format_ext}"
        self.output_file_path = str(output_dir / filename)

        logger.info(f"Output file: {self.output_file_path}")

    def _save_to_file(self) -> None:
        """ファイルに保存"""
        if not self.output_file_path:
            return

        try:
            with open(self.output_file_path, "w", encoding="utf-8") as f:
                # ヘッダー
                header = f"# 議事録 - {datetime.datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n\n"
                f.write(header + self.transcript_text)

            logger.debug(f"Saved to {self.output_file_path}")

        except Exception as e:
            logger.error(f"Failed to save file: {e}")

    def _copy_to_clipboard(self) -> None:
        """クリップボードにコピー"""
        try:
            pyperclip.copy(self.transcript_text)
            self.status_label.configure(text="状態: クリップボードにコピーしました")
            self.after(3000, lambda: self.status_label.configure(text="状態: 待機中"))

        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")

    def _open_settings(self) -> None:
        """設定ダイアログを開く"""
        # TODO: Phase 2で実装
        self.status_label.configure(text="設定ダイアログは Phase 2 で実装予定")
        self.after(3000, lambda: self.status_label.configure(text="状態: 待機中"))

    def cleanup(self) -> None:
        """クリーンアップ"""
        if self.recorder:
            self.recorder.cleanup()
        logger.info("MainWindow cleaned up")

    def on_closing(self) -> None:
        """ウィンドウクローズ時の処理"""
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_recording()

        self.cleanup()
        self.destroy()
