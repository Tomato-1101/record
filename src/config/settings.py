"""
設定管理モジュール
YAMLファイルと環境変数から設定を読み込む
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv
from src.utils.logger import logger


class Settings:
    """アプリケーション設定クラス"""

    def __init__(self, config_file: str = "config/default.yaml"):
        """
        設定の初期化

        Args:
            config_file: 設定ファイルのパス
        """
        # .envファイルから環境変数を読み込み
        load_dotenv()

        # 設定ファイルの読み込み
        self.config_file = config_file
        self.config: Dict[str, Any] = self._load_config(config_file)

        # APIキーの取得と検証
        self._load_api_keys()

        logger.info(f"Settings loaded from {config_file}")

    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """
        YAMLファイルから設定を読み込む

        Args:
            config_file: 設定ファイルのパス

        Returns:
            設定の辞書
        """
        config_path = Path(config_file)
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_file}. Using default settings.")
            return self._get_default_config()

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return config or {}

    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を返す"""
        return {
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "format": "paInt16"
            },
            "transcription": {
                "chunk_duration_sec": 30,
                "model": "whisper-groq",
                "language": "ja"
            },
            "output": {
                "directory": "output",
                "format": "txt",
                "auto_save": True,
                "file_prefix": "transcript_"
            },
            "ui": {
                "language": "ja",
                "theme": "dark"
            },
            "logging": {
                "level": "INFO",
                "file": "logs/app.log",
                "max_size_mb": 10,
                "backup_count": 3
            }
        }

    def _load_api_keys(self) -> None:
        """環境変数からAPIキーを読み込む"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")

        # APIキーの検証（警告のみ、エラーにはしない）
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not found in .env file")
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not found in .env file")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得

        Args:
            key_path: 設定キーのパス（例: "audio.sample_rate"）
            default: デフォルト値

        Returns:
            設定値
        """
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default

        return value if value is not None else default

    def save(self, config_file: Optional[str] = None) -> None:
        """
        設定をYAMLファイルに保存

        Args:
            config_file: 保存先ファイルパス（Noneの場合は読み込み元に保存）
        """
        save_path = Path(config_file or self.config_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"Settings saved to {save_path}")

    def update(self, key_path: str, value: Any) -> None:
        """
        設定値を更新

        Args:
            key_path: 設定キーのパス（例: "audio.sample_rate"）
            value: 新しい値
        """
        keys = key_path.split(".")
        config = self.config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value
        logger.debug(f"Setting updated: {key_path} = {value}")

    @property
    def audio_settings(self) -> Dict[str, Any]:
        """音声設定を取得"""
        return self.config.get("audio", {})

    @property
    def transcription_settings(self) -> Dict[str, Any]:
        """文字起こし設定を取得"""
        return self.config.get("transcription", {})

    @property
    def output_settings(self) -> Dict[str, Any]:
        """出力設定を取得"""
        return self.config.get("output", {})

    @property
    def ui_settings(self) -> Dict[str, Any]:
        """UI設定を取得"""
        return self.config.get("ui", {})

    @property
    def logging_settings(self) -> Dict[str, Any]:
        """ログ設定を取得"""
        return self.config.get("logging", {})


# グローバル設定インスタンス（シングルトンパターン）
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    グローバル設定インスタンスを取得

    Returns:
        Settings: 設定インスタンス
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_settings(config_file: str = "config/default.yaml") -> Settings:
    """
    設定を初期化

    Args:
        config_file: 設定ファイルのパス

    Returns:
        Settings: 設定インスタンス
    """
    global _settings
    _settings = Settings(config_file)
    return _settings
