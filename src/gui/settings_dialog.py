"""
設定ダイアログ
"""
import customtkinter as ctk
from typing import Optional, Callable
from src.config.settings import Settings
from src.locales.locale_manager import get_locale_manager
from src.utils.logger import logger


class SettingsDialog(ctk.CTkToplevel):
    """設定ダイアログクラス"""

    def __init__(self, parent, settings: Settings, on_save: Optional[Callable] = None):
        """
        設定ダイアログの初期化

        Args:
            parent: 親ウィンドウ
            settings: 設定オブジェクト
            on_save: 保存時のコールバック
        """
        super().__init__(parent)

        self.settings = settings
        self.on_save = on_save
        self.locale = get_locale_manager()

        # ウィンドウ設定
        self.title(self.locale.get("settings_title"))
        self.geometry("500x600")
        self.resizable(False, False)

        # モーダルダイアログにする
        self.transient(parent)
        self.grab_set()

        # 設定値の一時保存用
        self.temp_settings = {}

        # UIのセットアップ
        self._setup_ui()

        # 現在の設定値を読み込み
        self._load_current_settings()

    def _setup_ui(self) -> None:
        """UIのセットアップ"""
        # メインフレーム
        main_frame = ctk.CTkScrollableFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 音声設定セクション
        self._create_audio_section(main_frame)

        # 文字起こし設定セクション
        self._create_transcription_section(main_frame)

        # VAD設定セクション
        self._create_vad_section(main_frame)

        # 出力設定セクション
        self._create_output_section(main_frame)

        # ボタンフレーム
        self._create_button_frame()

    def _create_audio_section(self, parent) -> None:
        """音声設定セクション"""
        section_label = ctk.CTkLabel(
            parent,
            text=f"▼ {self.locale.get('settings_audio')}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        section_label.pack(anchor="w", pady=(10, 5))

        # 入力デバイス選択（Phase 2では簡易実装）
        device_frame = ctk.CTkFrame(parent)
        device_frame.pack(fill="x", pady=5)

        device_label = ctk.CTkLabel(
            device_frame,
            text=self.locale.get("settings_device"),
            width=150
        )
        device_label.pack(side="left", padx=10)

        self.device_combo = ctk.CTkComboBox(
            device_frame,
            values=["デフォルト"],
            state="readonly",
            width=250
        )
        self.device_combo.pack(side="left", padx=10)

    def _create_transcription_section(self, parent) -> None:
        """文字起こし設定セクション"""
        section_label = ctk.CTkLabel(
            parent,
            text=f"▼ {self.locale.get('settings_transcription')}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        section_label.pack(anchor="w", pady=(20, 5))

        # チャンク間隔
        chunk_frame = ctk.CTkFrame(parent)
        chunk_frame.pack(fill="x", pady=5)

        chunk_label = ctk.CTkLabel(
            chunk_frame,
            text=self.locale.get("settings_chunk_duration"),
            width=150
        )
        chunk_label.pack(side="left", padx=10)

        self.chunk_combo = ctk.CTkComboBox(
            chunk_frame,
            values=["30秒", "60秒"],
            state="readonly",
            width=250
        )
        self.chunk_combo.pack(side="left", padx=10)

        # APIモデル選択
        model_frame = ctk.CTkFrame(parent)
        model_frame.pack(fill="x", pady=5)

        model_label = ctk.CTkLabel(
            model_frame,
            text=self.locale.get("settings_model"),
            width=150
        )
        model_label.pack(side="left", padx=10)

        self.model_combo = ctk.CTkComboBox(
            model_frame,
            values=[
                "Whisper (Groq)",
                "gpt-4o-transcribe",
                "gpt-4o-diarize"
            ],
            state="readonly",
            width=250
        )
        self.model_combo.pack(side="left", padx=10)

        # 言語選択
        lang_frame = ctk.CTkFrame(parent)
        lang_frame.pack(fill="x", pady=5)

        lang_label = ctk.CTkLabel(
            lang_frame,
            text=self.locale.get("settings_language"),
            width=150
        )
        lang_label.pack(side="left", padx=10)

        self.lang_combo = ctk.CTkComboBox(
            lang_frame,
            values=["日本語 (ja)", "中文 (zh)", "English (en)"],
            state="readonly",
            width=250
        )
        self.lang_combo.pack(side="left", padx=10)

    def _create_vad_section(self, parent) -> None:
        """VAD設定セクション"""
        section_label = ctk.CTkLabel(
            parent,
            text=f"▼ {self.locale.get('settings_vad')}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        section_label.pack(anchor="w", pady=(20, 5))

        # VAD有効化チェックボックス
        vad_frame = ctk.CTkFrame(parent)
        vad_frame.pack(fill="x", pady=5)

        self.vad_enable_checkbox = ctk.CTkCheckBox(
            vad_frame,
            text=self.locale.get("settings_vad_enable")
        )
        self.vad_enable_checkbox.pack(side="left", padx=10)

        # VAD感度スライダー
        sensitivity_frame = ctk.CTkFrame(parent)
        sensitivity_frame.pack(fill="x", pady=5)

        sensitivity_label = ctk.CTkLabel(
            sensitivity_frame,
            text=self.locale.get("settings_vad_sensitivity"),
            width=150
        )
        sensitivity_label.pack(side="left", padx=10)

        self.vad_sensitivity_slider = ctk.CTkSlider(
            sensitivity_frame,
            from_=0,
            to=2,
            number_of_steps=2,
            width=200
        )
        self.vad_sensitivity_slider.pack(side="left", padx=10)

        self.vad_sensitivity_label = ctk.CTkLabel(
            sensitivity_frame,
            text=self.locale.get("settings_sensitivity_medium"),
            width=50
        )
        self.vad_sensitivity_label.pack(side="left", padx=5)

        # スライダーの変更時にラベルを更新
        self.vad_sensitivity_slider.configure(command=self._update_vad_label)

    def _create_output_section(self, parent) -> None:
        """出力設定セクション"""
        section_label = ctk.CTkLabel(
            parent,
            text=f"▼ {self.locale.get('settings_output')}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        section_label.pack(anchor="w", pady=(20, 5))

        # 出力フォーマット
        format_frame = ctk.CTkFrame(parent)
        format_frame.pack(fill="x", pady=5)

        format_label = ctk.CTkLabel(
            format_frame,
            text=self.locale.get("settings_output_format"),
            width=150
        )
        format_label.pack(side="left", padx=10)

        self.format_combo = ctk.CTkComboBox(
            format_frame,
            values=["txt", "md", "json"],
            state="readonly",
            width=250
        )
        self.format_combo.pack(side="left", padx=10)

    def _create_button_frame(self) -> None:
        """ボタンフレーム"""
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=20, pady=10)

        # キャンセルボタン
        cancel_button = ctk.CTkButton(
            button_frame,
            text=self.locale.get("btn_cancel"),
            width=100,
            command=self._on_cancel
        )
        cancel_button.pack(side="right", padx=10)

        # 保存ボタン
        save_button = ctk.CTkButton(
            button_frame,
            text=self.locale.get("btn_save"),
            width=100,
            command=self._on_save
        )
        save_button.pack(side="right", padx=10)

    def _load_current_settings(self) -> None:
        """現在の設定値を読み込み"""
        # チャンク間隔
        chunk_duration = self.settings.get("transcription.chunk_duration_sec", 30)
        self.chunk_combo.set("30秒" if chunk_duration == 30 else "60秒")

        # APIモデル
        model = self.settings.get("transcription.model", "whisper-groq")
        model_map = {
            "whisper-groq": "Whisper (Groq)",
            "gpt-4o-transcribe": "gpt-4o-transcribe",
            "gpt-4o-diarize": "gpt-4o-diarize"
        }
        self.model_combo.set(model_map.get(model, "Whisper (Groq)"))

        # 言語
        language = self.settings.get("transcription.language", "ja")
        lang_map = {
            "ja": "日本語 (ja)",
            "zh": "中文 (zh)",
            "en": "English (en)"
        }
        self.lang_combo.set(lang_map.get(language, "日本語 (ja)"))

        # VAD
        vad_enabled = self.settings.get("vad.enabled", False)
        self.vad_enable_checkbox.select() if vad_enabled else self.vad_enable_checkbox.deselect()

        vad_aggressiveness = self.settings.get("vad.aggressiveness", 2)
        self.vad_sensitivity_slider.set(vad_aggressiveness)
        self._update_vad_label(vad_aggressiveness)

        # 出力フォーマット
        output_format = self.settings.get("output.format", "txt")
        self.format_combo.set(output_format)

    def _update_vad_label(self, value) -> None:
        """VAD感度ラベルを更新"""
        value = int(float(value))
        label_map = {
            0: "settings_sensitivity_low",
            1: "settings_sensitivity_medium",
            2: "settings_sensitivity_high"
        }
        self.vad_sensitivity_label.configure(text=self.locale.get(label_map.get(value, "settings_sensitivity_medium")))

    def _on_save(self) -> None:
        """保存ボタンクリック時"""
        try:
            # チャンク間隔
            chunk_text = self.chunk_combo.get()
            chunk_duration = 30 if "30" in chunk_text else 60
            self.settings.update("transcription.chunk_duration_sec", chunk_duration)

            # APIモデル
            model_text = self.model_combo.get()
            model_map = {
                "Whisper (Groq)": "whisper-groq",
                "gpt-4o-transcribe": "gpt-4o-transcribe",
                "gpt-4o-diarize": "gpt-4o-diarize"
            }
            model = model_map.get(model_text, "whisper-groq")
            self.settings.update("transcription.model", model)

            # 言語
            lang_text = self.lang_combo.get()
            if "ja" in lang_text:
                language = "ja"
            elif "zh" in lang_text:
                language = "zh"
            else:
                language = "en"
            self.settings.update("transcription.language", language)

            # VAD
            vad_enabled = self.vad_enable_checkbox.get() == 1
            self.settings.update("vad.enabled", vad_enabled)

            vad_aggressiveness = int(self.vad_sensitivity_slider.get())
            self.settings.update("vad.aggressiveness", vad_aggressiveness)

            # 出力フォーマット
            output_format = self.format_combo.get()
            self.settings.update("output.format", output_format)

            # 設定を保存
            self.settings.save()

            logger.info("Settings saved successfully")

            # コールバック実行
            if self.on_save:
                self.on_save()

            # ダイアログを閉じる
            self.destroy()

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def _on_cancel(self) -> None:
        """キャンセルボタンクリック時"""
        self.destroy()
