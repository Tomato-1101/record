# 長時間議事録リアルタイム文字起こしアプリ 開発プロンプト

## 📋 プロジェクト概要

Windows PC 向けの長時間（最大 2 時間以上）議事録録音・リアルタイム文字起こしアプリケーションを開発してください。

---

## 🎯 コア要件

### 1. 基本機能

- **対象プラットフォーム**: Windows PC（初期開発対象）
- **録音時間**: 2 時間以上の連続録音に対応
- **自動保存**: 文字起こし結果はリアルタイムでファイルに自動保存（手動保存ボタン不要）
- **動作モード**: リアルタイム文字起こし（数秒〜1 分程度の遅延許容）

### 2. 文字起こしモデル（3 種類から選択）

| モデル                        | API        | 特徴                         | 料金             |
| ----------------------------- | ---------- | ---------------------------- | ---------------- |
| **Whisper Large V3 Turbo**    | Groq API   | 高速・無料枠あり             | 無料〜$0.04/時間 |
| **gpt-4o-transcribe**         | OpenAI API | 高精度                       | 有料             |
| **gpt-4o-transcribe-diarize** | OpenAI API | 話者分離（誰が話したか識別） | 有料             |

**API 設定:**

- **Whisper**: Groq API を使用（高速・無料枠: 2 時間/時間）
  - エンドポイント: `https://api.groq.com/openai/v1/audio/transcriptions`
  - モデル: `whisper-large-v3-turbo`
- **gpt-4o-transcribe / gpt-4o-transcribe-diarize**: OpenAI 公式 API を使用
  - エンドポイント: `https://api.openai.com/v1/audio/transcriptions`

**話者分離（gpt-4o-transcribe-diarize）の実装:**

```python
# OpenAI API リクエスト例
response = client.audio.transcriptions.create(
    model="gpt-4o-transcribe-diarize",
    file=audio_file,
    response_format="diarized_json",  # 必須: 話者ラベル取得
    chunking_strategy="auto"          # 30秒超の音声には必須
)

# レスポンス例
# {
#   "segments": [
#     {"speaker": "SPEAKER_0", "start": 0.0, "end": 3.5, "text": "本日の会議を始めます"},
#     {"speaker": "SPEAKER_1", "start": 3.8, "end": 7.2, "text": "よろしくお願いします"}
#   ]
# }
```

**話者ラベル付き出力フォーマット:**

```
[00:00:00] [話者A] 本日の会議を始めます。
[00:00:04] [話者B] よろしくお願いします。
[00:00:10] [話者A] まず最初の議題について説明します。
```

### 3. チャンク分割処理（最重要）

録音を**中断せずに**、以下の方式で文字起こしを実行：

```
[録音開始] ─────────────────────────────────────────────→ [録音継続中]
     │                │                │                │
     ├── chunk1 ──────┤                │                │
     │   (30s/60s)    ├── chunk2 ──────┤                │
     │                │   (30s/60s)    ├── chunk3 ──────┤
     │                │                │   (30s/60s)    │
     ▼                ▼                ▼                ▼
   [API送信]       [API送信]       [API送信]       [API送信]
     │                │                │                │
     ▼                ▼                ▼                ▼
   [テキスト1]     [テキスト2]     [テキスト3]     [テキスト4]
```

**実装要件:**

- チャンク間隔をユーザーが設定可能（30 秒 / 60 秒 / カスタム値）
- 録音スレッドと文字起こしスレッドを分離（非同期処理）
- 音声データはメモリ上でキュー管理し、処理済みチャンクは適切に解放
- チャンク境界での音声切れを防ぐため、オーバーラップ処理を検討

### 4. VAD（Voice Activity Detection）

音声区間検出を実装：

- 無音区間の自動検出・スキップ
- 発話開始/終了の検知
- VAD ライブラリ: `webrtcvad` または `silero-vad` を推奨
- VAD 感度をユーザーが調整可能（低/中/高）

**VAD 活用方法:**

- 無音が続く場合は API 送信をスキップ（コスト削減）
- 発話中はチャンク境界で切らない（文の途中で切れることを防止）

---

## 🏗️ 技術アーキテクチャ

### 推奨技術スタック

```
┌─────────────────────────────────────────────────────────┐
│                      GUI Layer                          │
│              (PyQt6 / tkinter / Electron)               │
├─────────────────────────────────────────────────────────┤
│                   Application Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Audio Thread │  │ VAD Process  │  │ API Thread   │  │
│  │  (Recording) │  │  (Detection) │  │(Transcription│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│         ▼                 ▼                  ▼          │
│  ┌────────────────────────────────────────────────────┐ │
│  │              Audio Buffer Manager                  │ │
│  │         (Queue-based Chunk Management)             │ │
│  └────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                    External Services                    │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │  Audio Capture   │  │      OpenAI API            │  │
│  │ (pyaudio/sounddevice) │  (Whisper / GPT-4o Audio)│  │
│  └──────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 必須ライブラリ

```python
# 音声処理
pyaudio>=0.2.13          # または sounddevice
numpy>=1.24.0
scipy>=1.10.0

# VAD
webrtcvad>=2.0.10        # 軽量VAD
# または
torch>=2.0.0             # silero-vad使用時
torchaudio>=2.0.0

# API通信
openai>=1.0.0
groq>=0.4.0              # Whisper用（無料・高速）
httpx>=0.24.0            # 非同期HTTP

# GUI（いずれか選択）
PyQt6>=6.5.0
# または
customtkinter>=5.2.0

# ユーティリティ
python-dotenv>=1.0.0
pydub>=0.25.1            # 音声フォーマット変換
pyperclip>=1.8.0         # クリップボードコピー
```

---

## 📁 推奨ディレクトリ構造

```
project/
├── src/
│   ├── main.py                 # エントリーポイント
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # メインウィンドウ
│   │   └── components/         # UIコンポーネント
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── recorder.py         # 録音処理
│   │   ├── buffer.py           # チャンク管理
│   │   └── vad.py              # VAD処理
│   ├── transcription/
│   │   ├── __init__.py
│   │   ├── whisper_client.py   # Whisper API
│   │   └── gpt4o_client.py     # GPT-4o Audio API
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # 設定管理
│   ├── locales/                # 多言語対応
│   │   ├── __init__.py
│   │   ├── ja.json             # 日本語
│   │   └── zh.json             # 中国語
│   └── utils/
│       ├── __init__.py
│       └── logger.py           # ログ処理
├── config/
│   └── default.yaml            # デフォルト設定
├── output/                     # 出力ファイル
├── .env                        # API Key（Git管理外）
├── .env.example                # API Keyサンプル
├── 進捗.md                     # 開発進捗管理ファイル
├── requirements.txt
└── README.md
```

---

## 🔧 詳細実装仕様

### 1. 録音モジュール (`audio/recorder.py`)

```python
class AudioRecorder:
    """
    連続録音を担当するクラス
    - 別スレッドで常時録音を継続
    - 指定間隔でチャンクをBufferManagerに送出
    - 録音停止まで中断なし
    """

    # 設定項目
    SAMPLE_RATE = 16000      # Whisper推奨
    CHANNELS = 1             # モノラル
    CHUNK_SIZE = 1024        # PyAudioバッファ
    FORMAT = pyaudio.paInt16
```

### 2. バッファマネージャ (`audio/buffer.py`)

```python
class AudioBufferManager:
    """
    音声チャンクのキュー管理
    - Thread-safe なキュー実装
    - チャンク間隔の計測・分割
    - メモリ効率的な管理
    """

    def __init__(self, chunk_duration_sec: int = 30):
        self.chunk_duration = chunk_duration_sec
        self.buffer_queue = queue.Queue()
```

### 3. VAD プロセッサ (`audio/vad.py`)

```python
class VADProcessor:
    """
    Voice Activity Detection
    - 発話区間の検出
    - 無音区間のフィルタリング
    - チャンク境界の最適化
    """

    # VAD設定
    FRAME_DURATION_MS = 30   # webrtcvad用
    AGGRESSIVENESS = 2       # 0-3 (高いほど厳格)
```

### 4. 文字起こしクライアント (`transcription/whisper_client.py`)

```python
class WhisperTranscriber:
    """
    OpenAI Whisper APIクライアント
    - 非同期でAPI呼び出し
    - レート制限対応
    - エラーリトライ
    """

    async def transcribe(self, audio_chunk: bytes) -> str:
        # Whisper API呼び出し
        pass
```

---

## 🖥️ GUI 要件

### 多言語対応（必須）

**UI 言語切り替え機能を実装:**

- 対応言語: **日本語 (ja)** / **中国語 (zh)**
- 切り替え方法: メインウィンドウに **[🌐 言語]** ボタンを配置
- ボタンを押すたびに日本語 ⇄ 中国語を切り替え
- 選択した言語は設定ファイルに保存し、次回起動時に復元
- すべての UI 要素（ボタン、ラベル、メッセージ等）を多言語化

**言語ファイル形式 (JSON):**

```json
// locales/ja.json
{
  "app_title": "議事録文字起こし",
  "btn_start": "録音開始",
  "btn_stop": "停止",
  "btn_copy": "コピー",
  "btn_settings": "設定",
  "btn_language": "中文",
  "status_recording": "録音中",
  "status_idle": "待機中",
  "label_duration": "録音時間"
}

// locales/zh.json
{
  "app_title": "会议记录转写",
  "btn_start": "开始录音",
  "btn_stop": "停止",
  "btn_copy": "复制",
  "btn_settings": "设置",
  "btn_language": "日本語",
  "status_recording": "录音中",
  "status_idle": "待机中",
  "label_duration": "录音时长"
}
```

### メインウィンドウ構成

```
┌─────────────────────────────────────────────────────────┐
│  📝 議事録文字起こし                    [🌐 中文] [─][□][×]│
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐│
│  │                                                     ││
│  │              リアルタイム文字起こし表示              ││
│  │                   (スクロール可能)                  ││
│  │                                                     ││
│  │                                                     ││
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│  録音時間: 00:45:32    状態: ● 録音中                   │
├─────────────────────────────────────────────────────────┤
│  [🎙️ 録音開始]  [⏹️ 停止]  [� コピー]  [⚙️ 設定]       │
└─────────────────────────────────────────────────────────┘
```

### 設定ダイアログ

```
┌─────────────────────────────────────────┐
│  ⚙️ 設定                           [×]  │
├─────────────────────────────────────────┤
│  ▼ 音声設定                             │
│    入力デバイス: [マイク (Realtek) ▼]   │
│                                         │
│  ▼ 文字起こし設定                       │
│    チャンク間隔: [30秒 ▼] (30秒/60秒)   │
│    APIモデル:    [Whisper (Groq)    ▼] │
│                  ├ Whisper (Groq)      │
│                  ├ gpt-4o-transcribe   │
│                  └ gpt-4o-diarize      │
│    言語:         [日本語 ▼]            │
│                                         │
│  ▼ VAD設定                              │
│    有効化: [✓]                          │
│    感度:   [●━━━━] 中                   │
│                                         │
│           [キャンセル]  [保存]          │
└─────────────────────────────────────────┘
```

---

## ⚡ パフォーマンス要件

| 項目               | 目標値                    |
| ------------------ | ------------------------- |
| 文字起こし遅延     | チャンク間隔 + 5 秒以内   |
| メモリ使用量       | 2 時間録音で 500MB 以下   |
| CPU 使用率         | 録音中 20%以下            |
| API 失敗時リトライ | 最大 3 回、指数バックオフ |

---

## 🔒 エラーハンドリング

1. **API 接続エラー**: リトライ後、ローカルキューに保存
2. **マイク切断**: 警告表示、自動再接続試行
3. **メモリ不足**: 古いチャンクの強制解放
4. **ファイル保存エラー**: 代替パスへの保存

---

## 📤 出力形式

### テキストファイル出力

```
# 議事録 - 2024年01月15日 14:00～16:00

[00:00:15] 本日の会議を始めます。
[00:00:32] まず最初の議題について説明します。
[00:01:45] 〇〇について、ご質問はありますか？
...
```

### 対応フォーマット

- `.txt` (プレーンテキスト)
- `.md` (Markdown)
- `.json` (タイムスタンプ付き JSON)
- `.srt` (字幕形式 - オプション)

---

## 🚀 開発フェーズ

### Phase 1: MVP（最小実装）

- [ ] 基本録音機能
- [ ] チャンク分割・API 送信
- [ ] シンプルなテキスト表示 GUI
- [ ] 設定ファイル対応

### Phase 2: 機能拡張

- [ ] VAD 実装
- [ ] 多言語 UI（日本語/中国語切り替え）
- [ ] 詳細設定 UI
- [ ] 出力フォーマット選択
- [ ] エラーリカバリー強化

### Phase 3: 最適化

- [ ] メモリ最適化
- [ ] 文字起こし精度向上（プロンプト調整）
- [ ] マルチスピーカー対応
- [ ] ホットキー対応

---

## 📊 開発ワークフロー（重要）

### 進捗管理ファイル

**`進捗.md` ファイルを作成し、以下のルールで運用:**

1. **作業開始時**: 必ず `進捗.md` を読み込んで現在の状態を確認
2. **タスク完了時**: 完了したタスクにチェックを入れ、作業内容を記録
3. **問題発生時**: 問題点と解決策を記録

**進捗.md のフォーマット:**

```markdown
# 開発進捗

## 現在のフェーズ

Phase 1: MVP

## 最終更新

2024-01-25 10:30

## 完了タスク

- [x] プロジェクト初期化 (2024-01-25)
- [x] 録音モジュール作成 (2024-01-25)

## 進行中タスク

- [ ] チャンク分割処理の実装
  - 現在: バッファマネージャのテスト中
  - 次のステップ: API 連携

## 未着手タスク

- [ ] GUI 実装
- [ ] VAD 実装

## 問題・メモ

- PyAudio のインストール時に VC++が必要
- Whisper API のレート制限に注意

## 次回やること

1. チャンク分割のテスト完了
2. Whisper API 接続確認
```

### Git 運用ルール

**以下のタイミングで Git コミットを実行:**

1. **フェーズ内の 1 タスク完了時**: 機能単位でコミット
2. **フェーズ完了時**: タグを付けてコミット
3. **重要な修正時**: バグ修正や設定変更時

**コミットメッセージ規則:**

```
[Phase X] タスク名: 簡潔な説明

例:
[Phase 1] 録音モジュール: 基本録音機能を実装
[Phase 1] チャンク処理: 30秒間隔での分割処理を追加
[Phase 2] 多言語対応: 日本語/中国語切り替え機能を実装
[Fix] VAD: 無音検出の感度調整
```

**Git 操作手順:**

```bash
# タスク完了時
git add .
git commit -m "[Phase X] タスク名: 説明"

# フェーズ完了時
git add .
git commit -m "[Phase X] 完了: フェーズXのすべてのタスクを完了"
git tag -a vX.0 -m "Phase X 完了"
```

### 開発サイクル

```
┌─────────────────────────────────────────────────────────┐
│  1. 進捗.md を確認 → 現在の状態を把握                   │
│         ↓                                               │
│  2. タスクを実装                                        │
│         ↓                                               │
│  3. 動作確認・テスト                                    │
│         ↓                                               │
│  4. 進捗.md を更新 → 完了タスクにチェック              │
│         ↓                                               │
│  5. Git コミット → 進捗保存                            │
│         ↓                                               │
│  6. 次のタスクへ → 1に戻る                             │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 追加指示

1. **コードスタイル**: PEP 8 準拠、型ヒント必須
2. **ログ出力**: 重要な処理ポイントでログ出力
3. **設定管理**: `.env`で API キー、YAML で動作設定
4. **テスト**: 主要機能のユニットテスト作成
5. **ドキュメント**: README.md に使用方法を記載

---

## 🔑 環境変数 (.env)

**セットアップ手順:**

1. `.env.example` を `.env` にコピー
2. 各 API キーを設定
3. `.env` は `.gitignore` に追加（Git 管理外にする）

```bash
# Windowsの場合
copy .env.example .env

# Mac/Linuxの場合
cp .env.example .env
```

**ファイル内容:**

```env
# OpenAI API Key (gpt-4o-transcribe / gpt-4o-transcribe-diarize 用)
# 取得: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx

# Groq API Key (Whisper 用 - 無料・高速)
# 取得: https://console.groq.com/keys
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
```

**Python での読み取り方法:**

```python
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

# APIキーを取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# キーが設定されているか確認
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY が .env に設定されていません")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY が .env に設定されていません")
```

---

## ✅ 完了条件

1. 2 時間の連続録音が安定動作する
2. 設定したチャンク間隔でリアルタイム文字起こしされる
3. 録音中断なくチャンク処理が行われる
4. VAD により無音区間がスキップされる
5. 結果がリアルタイムでファイルに自動保存される
6. クリップボードへのコピー機能が動作する
7. gpt-4o-transcribe-diarize 使用時、話者ラベルが正しく表示される
8. 3 つのモデル（Whisper@Groq、gpt-4o-transcribe、gpt-4o-transcribe-diarize）が切り替え可能
9. UI 言語（日本語/中国語）が切り替え可能
10. エラー時も録音データが失われない
