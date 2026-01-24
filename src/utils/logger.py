"""
ログ処理モジュール
loguruを使用した統一的なログ管理
"""
import os
import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_file: str = "logs/app.log", level: str = "INFO",
                 max_size_mb: int = 10, backup_count: int = 3) -> None:
    """
    ロガーの初期設定

    Args:
        log_file: ログファイルのパス
        level: ログレベル (DEBUG | INFO | WARNING | ERROR)
        max_size_mb: ログファイルの最大サイズ（MB）
        backup_count: バックアップファイル数
    """
    # デフォルトハンドラを削除
    logger.remove()

    # コンソール出力設定
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )

    # ログディレクトリの作成
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # ファイル出力設定（ローテーション付き）
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        rotation=f"{max_size_mb} MB",
        retention=backup_count,
        compression="zip",
        encoding="utf-8"
    )

    logger.info(f"Logger initialized: level={level}, file={log_file}")


def get_logger(name: str = __name__):
    """
    ロガーインスタンスを取得

    Args:
        name: ロガー名（通常は __name__ を使用）

    Returns:
        logger: loguruのロガーインスタンス
    """
    return logger.bind(name=name)


# モジュールレベルでのエクスポート
__all__ = ["setup_logger", "get_logger", "logger"]
