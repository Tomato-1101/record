"""
議事録リアルタイム文字起こしアプリ
エントリーポイント（ターミナルなし起動用）
"""
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# カレントディレクトリをプロジェクトルートに変更
os.chdir(str(project_root))

from src.utils.logger import setup_logger
from src.config.settings import init_settings, get_settings
from src.gui.main_window import MainWindow


def main():
    """メイン関数"""
    try:
        # 設定の初期化
        settings = init_settings("config/default.yaml")

        # ロガーの初期化
        log_settings = settings.logging_settings
        setup_logger(
            log_file=log_settings.get("file", "logs/app.log"),
            level=log_settings.get("level", "INFO"),
            max_size_mb=log_settings.get("max_size_mb", 10),
            backup_count=log_settings.get("backup_count", 3)
        )

        # メインウィンドウの作成と起動
        app = MainWindow(settings)
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()

    except Exception as e:
        # エラーをログファイルに記録
        from src.utils.logger import logger
        logger.exception(f"Application crashed: {e}")

        # エラーメッセージをファイルにも保存
        import datetime
        error_log = project_root / "logs" / "error.log"
        error_log.parent.mkdir(parents=True, exist_ok=True)
        with open(error_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"[{datetime.datetime.now()}] Application Error\n")
            f.write(f"{'='*50}\n")
            f.write(f"{e}\n")
            import traceback
            f.write(traceback.format_exc())


if __name__ == "__main__":
    main()
