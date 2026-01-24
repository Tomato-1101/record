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

## インストール

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd record
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

**注意**: Windows環境でPyAudioのインストールに失敗する場合は、以下のいずれかの方法を試してください:

- [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)からwhlファイルをダウンロードしてインストール
- Visual C++ Build Toolsをインストール

### 3. APIキーの設定

`.env.example`を`.env`にコピーし、APIキーを設定します:

```bash
# Windowsの場合
copy .env.example .env

# Mac/Linuxの場合
cp .env.example .env
```

`.env`ファイルを編集し、APIキーを設定:

```env
# OpenAI API Key (gpt-4o-transcribe / gpt-4o-transcribe-diarize 用)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx

# Groq API Key (Whisper 用 - 無料・高速)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
```

**APIキーの取得方法:**
- OpenAI: https://platform.openai.com/api-keys
- Groq: https://console.groq.com/keys

## 使い方

### アプリケーションの起動

```bash
python src/main.py
```

### 基本操作

1. **録音開始**: 「🎙️ 録音開始」ボタンをクリック
2. **録音停止**: 「⏹️ 停止」ボタンをクリック
3. **テキストコピー**: 「📋 コピー」ボタンでクリップボードにコピー
4. **設定**: 「⚙️ 設定」ボタンで設定画面を開く（Phase 2で実装予定）

### 文字起こし結果の保存

- 文字起こし結果は `output/` ディレクトリに自動保存されます
- ファイル名形式: `transcript_YYYYMMDD_HHMMSS.txt`

## 設定

### config/default.yaml

アプリケーションの動作設定は `config/default.yaml` で変更できます:

```yaml
# 文字起こし設定
transcription:
  chunk_duration_sec: 30  # チャンク間隔（秒）30または60
  model: "whisper-groq"   # whisper-groq | gpt-4o-transcribe | gpt-4o-diarize
  language: "ja"          # 文字起こし言語

# 音声設定
audio:
  sample_rate: 16000  # サンプルレート
  channels: 1         # チャンネル数（1=モノラル）

# 出力設定
output:
  directory: "output"   # 出力ディレクトリ
  format: "txt"         # 出力フォーマット
  auto_save: true       # 自動保存
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

### Phase 2: 機能拡張（予定）
- [ ] VAD（Voice Activity Detection）実装
- [ ] 多言語UI（日本語/中国語切り替え）
- [ ] 詳細設定UI
- [ ] 出力フォーマット選択
- [ ] エラーリカバリー強化

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
