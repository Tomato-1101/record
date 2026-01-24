"""
ローカライゼーション管理モジュール
多言語対応のためのリソース管理
"""
import json
from pathlib import Path
from typing import Dict, Optional
from src.utils.logger import logger


class LocaleManager:
    """言語リソース管理クラス"""

    def __init__(self, language: str = "ja"):
        """
        ローカライゼーションマネージャの初期化

        Args:
            language: 言語コード（ja | zh）
        """
        self.language = language
        self.translations: Dict[str, str] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """言語リソースファイルを読み込む"""
        locale_dir = Path(__file__).parent
        locale_file = locale_dir / f"{self.language}.json"

        if not locale_file.exists():
            logger.warning(f"Locale file not found: {locale_file}, falling back to ja")
            locale_file = locale_dir / "ja.json"

        try:
            with open(locale_file, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
            logger.info(f"Loaded translations for language: {self.language}")
        except Exception as e:
            logger.error(f"Failed to load translations: {e}")
            self.translations = {}

    def get(self, key: str, default: Optional[str] = None) -> str:
        """
        翻訳テキストを取得

        Args:
            key: 翻訳キー
            default: デフォルト値

        Returns:
            翻訳されたテキスト
        """
        return self.translations.get(key, default or key)

    def set_language(self, language: str) -> None:
        """
        言語を切り替える

        Args:
            language: 言語コード（ja | zh）
        """
        if language != self.language:
            self.language = language
            self._load_translations()
            logger.info(f"Language changed to: {language}")

    def get_current_language(self) -> str:
        """
        現在の言語を取得

        Returns:
            言語コード
        """
        return self.language

    def toggle_language(self) -> str:
        """
        言語を切り替える（日本語 ⇄ 中国語）

        Returns:
            新しい言語コード
        """
        new_language = "zh" if self.language == "ja" else "ja"
        self.set_language(new_language)
        return new_language


# グローバルインスタンス（シングルトンパターン）
_locale_manager: Optional[LocaleManager] = None


def get_locale_manager(language: Optional[str] = None) -> LocaleManager:
    """
    グローバルローカライゼーションマネージャを取得

    Args:
        language: 言語コード（初回のみ有効）

    Returns:
        LocaleManager インスタンス
    """
    global _locale_manager
    if _locale_manager is None:
        _locale_manager = LocaleManager(language or "ja")
    elif language and language != _locale_manager.language:
        _locale_manager.set_language(language)
    return _locale_manager


def init_locale_manager(language: str = "ja") -> LocaleManager:
    """
    ローカライゼーションマネージャを初期化

    Args:
        language: 言語コード

    Returns:
        LocaleManager インスタンス
    """
    global _locale_manager
    _locale_manager = LocaleManager(language)
    return _locale_manager
