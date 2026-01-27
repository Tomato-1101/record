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
from src.locales.locale_manager import get_locale_manager
from src.gui.settings_dialog import SettingsDialog
from src.utils.output_formatter import OutputFormatter, TranscriptBuilder


class MainWindow(ctk.CTk):
    """メインウィンドウクラス"""

    def __init__(self, settings: Settings):
        super().__init__()

        self.settings = settings
        self.recorder: Optional[AudioRecorder] = None
        self.buffer_manager: Optional[AudioBufferManager] = None
        self.transcriber: Optional[any] = None

        # 文字起こしテキストビルダー
        self.transcript_builder = TranscriptBuilder()
        self.transcript_text = ""  # 後方互換性のため保持
        self.output_file_path: Optional[str] = None

        # 録音状態管理
        self.is_recording = False
        self.is_paused = False
        self.test_mode = False  # テストモード
        self.audio_buffer_for_test = bytearray()  # テストモード用音声バッファ

        # 話者カラーマッピング（DIARIZEモデル用）
        self.speaker_colors = [
            "#3B82F6",  # Blue
            "#10B981",  # Green
            "#F59E0B",  # Orange
            "#EF4444",  # Red
            "#8B5CF6",  # Purple
            "#EC4899",  # Pink
            "#14B8A6",  # Teal
            "#F97316",  # Orange-red
        ]
        self.speaker_color_map = {}  # 話者名 -> 色のマッピング
        self.speaker_history = {}  # API話者ID → 一貫性のあるラベル
        self.last_speaker = None  # 最後の話者

        # ローカライゼーションマネージャ
        ui_language = self.settings.get("ui.language", "ja")
        self.locale = get_locale_manager(ui_language)

        # UIのセットアップ
        self._setup_ui()
        self._setup_recorder()

        logger.info("MainWindow initialized")

    def _setup_ui(self) -> None:
        """UIのセットアップ"""
        # ウィンドウ設定
        self.title(self.locale.get("app_title"))
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

        self.title_label = ctk.CTkLabel(
            title_frame,
            text=f"📝 {self.locale.get('app_title')}",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(side="left", padx=20, pady=10)

        # 言語切り替えボタン
        self.language_button = ctk.CTkButton(
            title_frame,
            text=self.locale.get("btn_language"),
            font=ctk.CTkFont(size=12),
            width=80,
            height=30,
            command=self._toggle_language
        )
        self.language_button.pack(side="right", padx=20, pady=10)

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

        # 話者変更セパレータスタイル
        try:
            self.text_box._textbox.tag_config("speaker_change", foreground="gray", justify="center")
        except:
            pass

    def _create_status_bar(self) -> None:
        """ステータスバーの作成"""
        status_frame = ctk.CTkFrame(self, height=40)
        status_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        status_frame.grid_propagate(False)

        # 録音時間
        self.time_label = ctk.CTkLabel(
            status_frame,
            text=f"{self.locale.get('label_duration')}: 00:00:00",
            font=ctk.CTkFont(size=12)
        )
        self.time_label.pack(side="left", padx=20)

        # 状態
        self.status_label = ctk.CTkLabel(
            status_frame,
            text=f"{self.locale.get('label_status')}: {self.locale.get('status_idle')}",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=20)

        # 録音言語
        language = self.settings.get("transcription.language", "ja")
        lang_display = {"ja": "日本語", "zh-CN": "中文简体", "zh": "中文简体", "en": "English"}.get(language, "日本語")
        self.language_label = ctk.CTkLabel(
            status_frame,
            text=f"{self.locale.get('label_language', '言語')}: {lang_display}",
            font=ctk.CTkFont(size=12)
        )
        self.language_label.pack(side="left", padx=20)

    def _create_control_panel(self) -> None:
        """コントロールパネルの作成"""
        control_frame = ctk.CTkFrame(self, height=80)
        control_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        control_frame.grid_propagate(False)

        # 録音開始ボタン
        self.start_button = ctk.CTkButton(
            control_frame,
            text=self.locale.get("btn_start"),
            font=ctk.CTkFont(size=14, weight="bold"),
            width=120,
            height=50,
            command=self._start_recording
        )
        self.start_button.pack(side="left", padx=5, pady=15)

        # 一時停止ボタン
        self.pause_button = ctk.CTkButton(
            control_frame,
            text=self.locale.get("btn_pause", "一時停止"),
            font=ctk.CTkFont(size=14, weight="bold"),
            width=120,
            height=50,
            command=self._pause_recording,
            state="disabled"
        )
        self.pause_button.pack(side="left", padx=5, pady=15)

        # 停止ボタン
        self.stop_button = ctk.CTkButton(
            control_frame,
            text=self.locale.get("btn_stop"),
            font=ctk.CTkFont(size=14, weight="bold"),
            width=120,
            height=50,
            command=self._stop_recording,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5, pady=15)

        # コピーボタン
        self.copy_button = ctk.CTkButton(
            control_frame,
            text=self.locale.get("btn_copy"),
            font=ctk.CTkFont(size=14),
            width=100,
            height=50,
            command=self._copy_to_clipboard
        )
        self.copy_button.pack(side="left", padx=5, pady=15)

        # 設定ボタン
        self.settings_button = ctk.CTkButton(
            control_frame,
            text=self.locale.get("btn_settings"),
            font=ctk.CTkFont(size=14),
            width=100,
            height=50,
            command=self._open_settings
        )
        self.settings_button.pack(side="left", padx=5, pady=15)

        # テストモードトグルボタン
        self.test_mode_button = ctk.CTkButton(
            control_frame,
            text=self.locale.get("btn_test_mode_off", "テストモード: OFF"),
            font=ctk.CTkFont(size=12),
            width=140,
            height=50,
            command=self._toggle_test_mode,
            fg_color="gray"
        )
        self.test_mode_button.pack(side="left", padx=5, pady=15)

    def _setup_recorder(self) -> None:
        """録音システムのセットアップ"""
        # バッファマネージャの作成
        chunk_duration = self.settings.get("transcription.chunk_duration_sec", 30)
        sample_rate = self.settings.get("audio.sample_rate", 16000)
        vad_aggressiveness = self.settings.get("vad.aggressiveness", 2)
        queue_maxsize = self.settings.get("audio.queue_maxsize", 20)
        chunk_overlap = self.settings.get("transcription.chunk_overlap_sec", 5)

        # 動的チャンク設定
        min_chunk_sec = self.settings.get("transcription.min_chunk_sec", 5)
        max_chunk_sec = self.settings.get("transcription.max_chunk_sec", 30)
        silence_threshold_ms = self.settings.get("transcription.silence_threshold_ms", 500)

        # VADは常に有効
        self.buffer_manager = AudioBufferManager(
            chunk_duration_sec=chunk_duration,
            sample_rate=sample_rate,
            channels=1,
            on_chunk_ready=self._on_chunk_ready,
            vad_enabled=True,  # 常にON
            vad_aggressiveness=vad_aggressiveness,
            queue_maxsize=queue_maxsize,
            chunk_overlap_sec=chunk_overlap,
            min_chunk_sec=min_chunk_sec,
            max_chunk_sec=max_chunk_sec,
            silence_threshold_ms=silence_threshold_ms
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
        sample_rate = self.settings.get("audio.sample_rate", 16000)
        channels = self.settings.get("audio.channels", 1)

        if model == "whisper-groq":
            if not self.settings.groq_api_key:
                logger.error("Groq API key not found")
                return

            self.transcriber = WhisperTranscriber(
                api_key=self.settings.groq_api_key,
                model_name=self.settings.get("transcription.whisper.model_name",
                                            "whisper-large-v3-turbo"),
                language=language,
                temperature=self.settings.get("transcription.whisper.temperature", 0.0),
                sample_rate=sample_rate,
                channels=channels,
                prompt_template="",
                use_context=False
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
                enable_diarization=enable_diarization,
                sample_rate=sample_rate,
                channels=channels,
                prompt_template="",
                use_context=False
            )

    def _remove_overlap_text(self, new_text: str) -> str:
        """
        オーバーラップによる重複テキストを削除

        Args:
            new_text: 新しいチャンクのテキスト

        Returns:
            重複削除後のテキスト
        """
        if not self.transcript_text:
            return new_text

        # 前のテキストの最後の50文字と新しいテキストを比較
        prev_tail = self.transcript_text[-50:] if len(self.transcript_text) > 50 else self.transcript_text

        # 重複部分を検出（最低5文字以上の一致）
        for i in range(len(prev_tail), 4, -1):
            suffix = prev_tail[-i:]
            if new_text.startswith(suffix):
                # 重複を削除
                deduplicated = new_text[i:]
                if deduplicated:
                    logger.debug(f"Removed overlap: '{suffix}' from new text")
                    return deduplicated
                else:
                    # 全体が重複している場合は空文字列を返す
                    logger.debug(f"New text is completely duplicated, skipping")
                    return ""

        return new_text

    def _on_chunk_ready(self, audio_chunk: bytes, timestamp: float) -> None:
        """
        チャンク準備完了時のコールバック

        Args:
            audio_chunk: 音声データ
            timestamp: タイムスタンプ
        """
        # テストモードの場合、音声データを保存
        if self.test_mode:
            self.audio_buffer_for_test.extend(audio_chunk)

        if not self.transcriber:
            logger.warning("Transcriber not initialized")
            return

        # 文字起こし実行
        text = self.transcriber.transcribe(audio_chunk, timestamp)

        if text:
            # 非常に短いテキスト（3文字未満）は無視（ノイズの可能性）
            if len(text.strip()) < 3:
                logger.debug(f"Ignoring short transcription: '{text}'")
                return

            # オーバーラップによる重複テキストを削除
            text = self._remove_overlap_text(text)
            if not text:
                logger.debug("Text is completely overlapped, skipping")
                return

            # TranscriptBuilderにチャンクを追加
            self.transcript_builder.add_chunk(text, timestamp)

            # 後方互換性のため
            self.transcript_text = self.transcript_builder.get_text()

            # UIを更新（メインスレッドで実行）
            # 既存のテキストがある場合はスペースを追加
            if self.transcript_text and self.transcript_text != text:
                formatted_text = " " + text
            else:
                formatted_text = text

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
        """テキスト表示を更新（話者名は色付き）"""
        import re

        # DIARIZEモデルの出力パターンを検出: 話者A: テキスト
        speaker_pattern = r'(話者[A-Z]):'

        # 話者変更を検出
        current_speaker = None
        match = re.search(speaker_pattern, text)
        if match:
            current_speaker = match.group(1)

            if self.last_speaker and self.last_speaker != current_speaker:
                # 話者が変わった - 視覚的セパレータを追加
                self.text_box.insert("end", "\n---\n", "speaker_change")

            self.last_speaker = current_speaker

        if re.search(speaker_pattern, text):
            # 話者名が含まれている場合、色付きで表示
            parts = re.split(speaker_pattern, text)

            for i, part in enumerate(parts):
                if re.match(r'話者[A-Z]', part):
                    # 話者名の場合、色を割り当てて表示
                    if part not in self.speaker_color_map:
                        color_index = len(self.speaker_color_map) % len(self.speaker_colors)
                        self.speaker_color_map[part] = self.speaker_colors[color_index]

                    color = self.speaker_color_map[part]

                    # タグを作成（まだ作成されていない場合）
                    tag_name = f"speaker_{part}"
                    try:
                        self.text_box.tag_config(tag_name, foreground=color, font=("", 14, "bold"))
                    except:
                        pass

                    # 話者名を色付きで挿入
                    start_index = self.text_box.index("end-1c")
                    self.text_box.insert("end", part)
                    end_index = self.text_box.index("end-1c")
                    self.text_box.tag_add(tag_name, start_index, end_index)
                else:
                    # 通常のテキスト
                    self.text_box.insert("end", part)
        else:
            # 通常のテキスト（話者なし）
            self.text_box.insert("end", text)

        self.text_box.see("end")  # 自動スクロール

    def _track_speaker(self, speaker_label: str) -> str:
        """
        話者ラベルを一貫性のあるものに変換

        Args:
            speaker_label: APIから返された話者ラベル（例: SPEAKER_0）

        Returns:
            一貫性のある話者ラベル（例: 話者A）
        """
        if speaker_label not in self.speaker_history:
            # 新しい話者 - 次の利用可能なラベルを割り当て
            existing_count = len(self.speaker_history)
            labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

            if existing_count < len(labels):
                consistent_label = f"話者{labels[existing_count]}"
            else:
                consistent_label = f"話者{existing_count + 1}"

            self.speaker_history[speaker_label] = consistent_label
            logger.info(f"New speaker detected: {speaker_label} -> {consistent_label}")

        return self.speaker_history[speaker_label]

    def _start_recording(self) -> None:
        """録音開始または再開"""
        try:
            # 一時停止から再開の場合
            if self.is_paused:
                self.is_paused = False
                self.is_recording = True

                # 録音再開
                self.recorder.start_recording()

                # UIの更新
                self.start_button.configure(state="disabled")
                self.pause_button.configure(state="normal", text=self.locale.get("btn_pause", "一時停止"))
                self.stop_button.configure(state="normal")
                self.status_label.configure(
                    text=f"{self.locale.get('label_status')}: {self.locale.get('status_recording')}"
                )

                # タイマー再開
                self._update_timer()

                logger.info("Recording resumed")

            # 新規開始の場合
            else:
                # テストモード用バッファをクリア
                if self.test_mode:
                    self.audio_buffer_for_test.clear()

                # TranscriptBuilderをクリア
                self.transcript_builder.clear()
                self.transcript_text = ""
                self.text_box.delete("1.0", "end")

                # 話者カラーマッピングをクリア
                self.speaker_color_map.clear()
                self.speaker_history.clear()
                self.last_speaker = None

                # 出力ファイルの準備
                self._prepare_output_file()

                # 録音開始
                self.recorder.start_recording()
                self.is_recording = True
                self.is_paused = False

                # UIの更新
                self.start_button.configure(state="disabled")
                self.pause_button.configure(state="normal")
                self.stop_button.configure(state="normal")
                self.status_label.configure(
                    text=f"{self.locale.get('label_status')}: {self.locale.get('status_recording')}"
                )

                # タイマー開始
                self._update_timer()

                logger.info("Recording started")

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.status_label.configure(
                text=f"{self.locale.get('label_status')}: {self.locale.get('error_recording_failed')}"
            )

    def _pause_recording(self) -> None:
        """録音一時停止"""
        try:
            # 録音一時停止
            self.recorder.stop_recording()
            self.is_paused = True
            self.is_recording = False

            # UIの更新
            self.start_button.configure(state="normal", text=self.locale.get("btn_resume", "再開"))
            self.pause_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.status_label.configure(
                text=f"{self.locale.get('label_status')}: {self.locale.get('status_paused', '一時停止中')}"
            )

            logger.info("Recording paused")

        except Exception as e:
            logger.error(f"Failed to pause recording: {e}")

    def _stop_recording(self) -> None:
        """録音完全停止"""
        try:
            # 録音停止
            self.recorder.stop_recording()
            self.is_recording = False
            self.is_paused = False

            # テストモードの場合、音声ファイルを保存
            if self.test_mode and len(self.audio_buffer_for_test) > 0:
                self._save_audio_file()

            # UIの更新
            self.start_button.configure(state="normal", text=self.locale.get("btn_start"))
            self.pause_button.configure(state="disabled")
            self.stop_button.configure(state="disabled")
            self.status_label.configure(
                text=f"{self.locale.get('label_status')}: {self.locale.get('status_idle')}"
            )

            logger.info("Recording stopped")

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")

    def _update_timer(self) -> None:
        """タイマー更新"""
        if self.recorder and self.recorder.is_recording:
            elapsed = self.recorder.get_elapsed_time()
            time_str = self._format_timestamp(elapsed)
            self.time_label.configure(text=f"{self.locale.get('label_duration')}: {time_str}")

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
            # 設定から出力フォーマットを取得
            format_type = self.settings.get("output.format", "txt")

            # メタデータを作成
            model_name = self.settings.get("transcription.model", "")
            elapsed = self.recorder.get_elapsed_time() if self.recorder else 0
            duration = self._format_timestamp(elapsed)

            metadata = self.transcript_builder.get_metadata(
                title="議事録",
                model=model_name,
                duration=duration
            )

            # フォーマットに応じて内容を整形
            text = self.transcript_builder.get_text()

            if format_type == "md":
                content = OutputFormatter.format_markdown(text, metadata)
            elif format_type == "json":
                chunks = self.transcript_builder.get_chunks()
                content = OutputFormatter.format_json(text, metadata, chunks)
            else:  # txt
                content = OutputFormatter.format_text(text, metadata)

            # ファイルに保存
            OutputFormatter.save_file(self.output_file_path, content, format_type)

        except Exception as e:
            logger.error(f"Failed to save file: {e}")

    def _copy_to_clipboard(self) -> None:
        """クリップボードにコピー"""
        try:
            if self.transcript_text:
                pyperclip.copy(self.transcript_text)
                logger.info(self.locale.get("message_copied"))
                # 一時的に通知を表示
                original_text = self.copy_button.cget("text")
                self.copy_button.configure(text="✓")
                self.after(1000, lambda: self.copy_button.configure(text=original_text))
            else:
                logger.warning(self.locale.get("message_no_text"))

        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")

    def _open_settings(self) -> None:
        """設定ダイアログを開く"""
        # 録音中は設定を変更できない
        if self.recorder and self.recorder.is_recording:
            logger.warning("Cannot change settings while recording")
            return

        # 設定ダイアログを開く
        dialog = SettingsDialog(self, self.settings, on_save=self._on_settings_saved)
        self.wait_window(dialog)

    def _on_settings_saved(self) -> None:
        """設定保存後のコールバック"""
        # 設定が変更されたので、録音システムを再構築
        logger.info("Settings changed, reinitializing recorder system")

        # 既存のレコーダーをクローズ（PyAudioは終了しない）
        if self.recorder:
            self.recorder.close()

        # 録音システムを再セットアップ
        self._setup_recorder()

        # 言語ラベルを更新
        language = self.settings.get("transcription.language", "ja")
        lang_display = {"ja": "日本語", "zh-CN": "中文简体", "zh": "中文简体", "en": "English"}.get(language, "日本語")
        self.language_label.configure(text=f"{self.locale.get('label_language', '言語')}: {lang_display}")

        logger.info("Recorder system reinitialized")

    def _toggle_language(self) -> None:
        """言語を切り替える"""
        new_language = self.locale.toggle_language()

        # 設定ファイルに保存
        self.settings.update("ui.language", new_language)
        self.settings.save()

        # UIを更新
        self._refresh_ui()

        logger.info(f"Language changed to: {new_language}")

    def _toggle_test_mode(self) -> None:
        """テストモードの切り替え"""
        self.test_mode = not self.test_mode

        if self.test_mode:
            self.test_mode_button.configure(
                text=self.locale.get("btn_test_mode_on", "テストモード: ON"),
                fg_color="green"
            )
            logger.info("Test mode enabled - audio will be saved to output/dev/")
        else:
            self.test_mode_button.configure(
                text=self.locale.get("btn_test_mode_off", "テストモード: OFF"),
                fg_color="gray"
            )
            logger.info("Test mode disabled")

    def _save_audio_file(self) -> None:
        """テストモード用の音声ファイルを保存"""
        try:
            import wave
            import datetime
            from pathlib import Path

            # output/devディレクトリを作成
            dev_dir = Path("output/dev")
            dev_dir.mkdir(parents=True, exist_ok=True)

            # ファイル名を生成（transcriptと同じタイムスタンプ）
            if self.output_file_path:
                # transcriptファイル名からタイムスタンプを抽出
                transcript_name = Path(self.output_file_path).stem
                timestamp = transcript_name.replace("transcript_", "")
                audio_filename = f"audio_{timestamp}.wav"
            else:
                # フォールバック
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_filename = f"audio_{timestamp}.wav"

            audio_path = dev_dir / audio_filename

            # WAVファイルとして保存
            with wave.open(str(audio_path), 'wb') as wav_file:
                wav_file.setnchannels(1)  # モノラル
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.settings.get("audio.sample_rate", 16000))
                wav_file.writeframes(bytes(self.audio_buffer_for_test))

            logger.info(f"Test audio saved to: {audio_path}")

        except Exception as e:
            logger.error(f"Failed to save audio file: {e}")

    def _refresh_ui(self) -> None:
        """UIテキストを再読み込み"""
        # ウィンドウタイトル
        self.title(self.locale.get("app_title"))

        # タイトルラベル
        self.title_label.configure(text=f"📝 {self.locale.get('app_title')}")

        # 言語ボタン
        self.language_button.configure(text=self.locale.get("btn_language"))

        # ステータスバー
        if self.recorder and self.recorder.is_recording:
            status_text = self.locale.get('status_recording')
        else:
            status_text = self.locale.get('status_idle')

        elapsed = self.recorder.get_elapsed_time() if self.recorder else 0
        time_str = self._format_timestamp(elapsed)
        self.time_label.configure(text=f"{self.locale.get('label_duration')}: {time_str}")
        self.status_label.configure(text=f"{self.locale.get('label_status')}: {status_text}")

        # 録音言語
        language = self.settings.get("transcription.language", "ja")
        lang_display = {"ja": "日本語", "zh-CN": "中文简体", "zh": "中文简体", "en": "English"}.get(language, "日本語")
        self.language_label.configure(text=f"{self.locale.get('label_language', '言語')}: {lang_display}")

        # ボタン
        if self.is_paused:
            self.start_button.configure(text=self.locale.get("btn_resume"))
        else:
            self.start_button.configure(text=self.locale.get("btn_start"))
        self.pause_button.configure(text=self.locale.get("btn_pause"))
        self.stop_button.configure(text=self.locale.get("btn_stop"))
        self.copy_button.configure(text=self.locale.get("btn_copy"))
        self.settings_button.configure(text=self.locale.get("btn_settings"))
        if self.test_mode:
            self.test_mode_button.configure(text=self.locale.get("btn_test_mode_on"))
        else:
            self.test_mode_button.configure(text=self.locale.get("btn_test_mode_off"))

    def cleanup(self) -> None:
        """クリーンアップ"""
        if self.recorder:
            self.recorder.cleanup()  # アプリ終了時はPyAudioも終了
        logger.info("MainWindow cleaned up")

    def on_closing(self) -> None:
        """ウィンドウクローズ時の処理"""
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_recording()

        self.cleanup()
        self.destroy()
