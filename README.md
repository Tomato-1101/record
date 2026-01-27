# 議事録リアルタイム文字起こしアプリ

Windows PC向けの長時間（2時間以上）議事録録音・リアルタイム文字起こしアプリケーション

## 特徴

- **長時間録音対応**: 2時間以上の連続録音に対応
- **リアルタイム文字起こし**: 30秒/60秒間隔でチャンク処理
- **3つの文字起こしモデル**:
  - Whisper Large V3 Turbo (Groq API) - 高速・無料枠あり
  - gpt-4o-transcribe (OpenAI API) - 高精度
  - gpt-4o-transcribe-diarize (OpenAI API) - 話者分離機能付き
- **自動保存**: 文字起こし結果をリアルタイムでファイルに自動保存
- **モダンなUI**: customtkinterによる軽量でモダンなインターフェース

## システム要件

- Windows PC
- Python 3.8以上
- マイク（音声入力デバイス）

## インストールと実行

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd record
```

### 2. 実行（Windows）

フォルダ内の `setup.bat` をダブルクリックして実行してください。

1. **環境構築**: 必要なライブラリ（Python仮想環境）が自動的にセットアップされます。
2. **APIキー設定**: 初回は `.env` ファイルが作成され、メモ帳で開かれます。ご自身のAPIキーを入力して保存してください。
3. **起動**: 設定完了後、自動的にアプリケーションが起動します。

※ 2回目以降も `setup.bat`（または `run.bat`）を実行するだけで起動できます。

### 手動インストール（Mac/Linux または上級者向け）

```bash
# 仮想環境の作成と有効化
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# 依存パッケージのインストール
pip install -r requirements.txt

# APIキーの設定
cp .env.example .env
# .envファイルを編集してAPIキーを設定

# 実行
python src/main.py
```

### APIキーについて

以下のサービスからAPIキーを取得して `.env` ファイルに設定してください：

- **OpenAI API Key**: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
  - 高精度な文字起こし (`gpt-4o-transcribe`) に使用
- **Groq API Key**: [https://console.groq.com/keys](https://console.groq.com/keys)
  - 高速・無料枠のある文字起こし (`whisper-groq`) に使用

## 使い方

### アプリケーションの起動

`setup.bat`（または `run.bat`）を実行してください。

### 基本操作

1. **録音開始**: 「🎙️ 録音開始」ボタンをクリック
2. **録音停止**: 「⏹️ 停止」ボタンをクリック
3. **テキストコピー**: 「📋 コピー」ボタンでクリップボードにコピー
4. **設定**: 「⚙️ 設定」ボタンで設定画面を開く
5. **言語切り替え**: タイトルバーの「中文」/「日本語」ボタンで言語切り替え

### 文字起こし結果の保存

- 文字起こし結果は `output/` ディレクトリに自動保存されます
- ファイル名形式: `transcript_YYYYMMDD_HHMMSS.txt`

## 設定

### config/default.yaml

アプリケーションの動作設定は `config/default.yaml` で変更できます:

```yaml
# 文字起こし設定
transcription:
  chunk_duration_sec: 30 # チャンク間隔（秒）30または60
  model: "whisper-groq" # whisper-groq | gpt-4o-transcribe | gpt-4o-diarize
  language: "ja" # 文字起こし言語

# 音声設定
audio:
  sample_rate: 16000 # サンプルレート
  channels: 1 # チャンネル数（1=モノラル）

# 出力設定
output:
  directory: "output" # 出力ディレクトリ
  format: "txt" # 出力フォーマット
  auto_save: true # 自動保存
```

## プロジェクト構造

```
record/
├── src/
│   ├── main.py                 # エントリーポイント
│   ├── gui/
│   │   └── main_window.py      # メインウィンドウ
│   ├── audio/
│   │   ├── recorder.py         # 録音処理
│   │   └── buffer.py           # チャンク管理
│   ├── transcription/
│   │   ├── whisper_client.py   # Whisper API
│   │   └── gpt4o_client.py     # GPT-4o API
│   ├── config/
│   │   └── settings.py         # 設定管理
│   └── utils/
│       └── logger.py           # ログ処理
├── config/
│   └── default.yaml            # デフォルト設定
├── output/                     # 出力ファイル
├── logs/                       # ログファイル
├── .env                        # APIキー（Git管理外）
├── requirements.txt            # 依存パッケージ
└── README.md                   # このファイル
```

## 開発ロードマップ

### Phase 1: MVP（完了）✅

- [x] 基本録音機能
- [x] チャンク分割・API送信
- [x] シンプルなテキスト表示GUI
- [x] 設定ファイル対応

### Phase 2: 機能拡張（完了）✅

- [x] VAD（Voice Activity Detection）実装
- [x] 多言語UI（日本語/中国語切り替え）
- [x] 詳細設定UI
- [x] 出力フォーマット選択（txt/md/json）
- [x] テキスト出力形式改善（タイムスタンプなし、連続出力）

### Phase 3: 最適化（予定）

- [ ] メモリ最適化
- [ ] 文字起こし精度向上
- [ ] マルチスピーカー対応
- [ ] ホットキー対応

## トラブルシューティング

### PyAudioのインストールエラー

Windows環境で `pip install pyaudio` が失敗する場合:

1. [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)から対応するwhlファイルをダウンロード
2. `pip install PyAudio‑0.2.13‑cp3XX‑cp3XX‑winXX.whl` でインストール

### APIエラー

- APIキーが正しく設定されているか確認してください（`.env`ファイル）
- APIの利用制限（レート制限）に達していないか確認してください

### 録音デバイスが認識されない

- マイクが正しく接続されているか確認してください
- Windowsの設定でマイクが有効になっているか確認してください

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します。大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## サポート

問題が発生した場合は、GitHubのissueページで報告してください。
