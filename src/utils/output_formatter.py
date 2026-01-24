"""
出力フォーマット管理モジュール
複数の出力形式（txt, md, json）に対応
"""
import json
import datetime
from typing import Dict, List
from pathlib import Path
from src.utils.logger import logger


class OutputFormatter:
    """出力フォーマッタークラス"""

    @staticmethod
    def format_text(transcript_text: str, metadata: Dict = None) -> str:
        """
        テキスト形式でフォーマット

        Args:
            transcript_text: 文字起こしテキスト
            metadata: メタデータ（タイトル、日時など）

        Returns:
            フォーマット済みテキスト
        """
        if metadata:
            title = metadata.get("title", "議事録")
            date_str = metadata.get("date", datetime.datetime.now().strftime('%Y年%m月%d日 %H:%M'))
            header = f"# {title} - {date_str}\n\n"
            return header + transcript_text
        return transcript_text

    @staticmethod
    def format_markdown(transcript_text: str, metadata: Dict = None) -> str:
        """
        Markdown形式でフォーマット

        Args:
            transcript_text: 文字起こしテキスト
            metadata: メタデータ

        Returns:
            Markdown形式のテキスト
        """
        if metadata:
            title = metadata.get("title", "議事録")
            date_str = metadata.get("date", datetime.datetime.now().strftime('%Y年%m月%d日 %H:%M'))
            duration = metadata.get("duration", "")
            model = metadata.get("model", "")

            markdown = f"# {title}\n\n"
            markdown += f"**日時**: {date_str}\n\n"

            if duration:
                markdown += f"**録音時間**: {duration}\n\n"

            if model:
                markdown += f"**文字起こしモデル**: {model}\n\n"

            markdown += "---\n\n"
            markdown += "## 内容\n\n"
            markdown += transcript_text + "\n"

            return markdown
        return f"## 内容\n\n{transcript_text}\n"

    @staticmethod
    def format_json(transcript_text: str, metadata: Dict = None, chunks: List[Dict] = None) -> str:
        """
        JSON形式でフォーマット

        Args:
            transcript_text: 文字起こしテキスト
            metadata: メタデータ
            chunks: チャンクごとの詳細情報

        Returns:
            JSON形式の文字列
        """
        output = {
            "transcript": transcript_text,
            "metadata": metadata or {},
            "chunks": chunks or []
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    @staticmethod
    def save_file(
        file_path: str,
        content: str,
        format_type: str = "txt"
    ) -> None:
        """
        ファイルに保存

        Args:
            file_path: ファイルパス
            content: 保存する内容
            format_type: フォーマットタイプ（txt | md | json）
        """
        try:
            # 拡張子を確認・修正
            path = Path(file_path)
            if path.suffix.lower() != f".{format_type}":
                path = path.with_suffix(f".{format_type}")

            # ディレクトリが存在しない場合は作成
            path.parent.mkdir(parents=True, exist_ok=True)

            # ファイルに書き込み
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Saved to {path}")

        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise


class TranscriptBuilder:
    """文字起こしテキストビルダークラス"""

    def __init__(self):
        """初期化"""
        self.text = ""
        self.chunks = []
        self.start_time = None

    def add_chunk(self, text: str, timestamp: float = 0.0) -> None:
        """
        チャンクを追加

        Args:
            text: テキスト
            timestamp: タイムスタンプ
        """
        if not self.start_time:
            self.start_time = datetime.datetime.now()

        # テキストを連続して追加
        formatted_text = text if not self.text else " " + text
        self.text += formatted_text

        # チャンク情報を保存
        self.chunks.append({
            "timestamp": timestamp,
            "text": text,
            "length": len(text)
        })

    def get_text(self) -> str:
        """
        文字起こしテキストを取得

        Returns:
            文字起こしテキスト
        """
        return self.text

    def get_metadata(self, title: str = "議事録", model: str = "", duration: str = "") -> Dict:
        """
        メタデータを取得

        Args:
            title: タイトル
            model: 使用モデル
            duration: 録音時間

        Returns:
            メタデータ
        """
        return {
            "title": title,
            "date": self.start_time.strftime('%Y年%m月%d日 %H:%M') if self.start_time else "",
            "model": model,
            "duration": duration,
            "total_chunks": len(self.chunks),
            "total_characters": len(self.text)
        }

    def get_chunks(self) -> List[Dict]:
        """
        チャンク情報を取得

        Returns:
            チャンク情報のリスト
        """
        return self.chunks

    def clear(self) -> None:
        """クリア"""
        self.text = ""
        self.chunks = []
        self.start_time = None
