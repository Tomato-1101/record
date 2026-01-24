# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Windows PC real-time transcription application for long-duration (2+ hours) meeting recordings. It continuously records audio, splits it into chunks (30/60 seconds), and sends them to transcription APIs (Groq Whisper or OpenAI GPT-4o Audio) for real-time text generation.

**Current Status**: Phase 2 (Feature Expansion) completed. VAD, multilingual UI, settings dialog, and multiple output formats implemented.

## Running the Application

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
copy .env.example .env
# Edit .env and add your OPENAI_API_KEY and GROQ_API_KEY

# Run the application
python src/main.py
```

### Testing
No automated tests yet. Manual testing workflow:
1. Launch the app with `python src/main.py`
2. Click "録音開始" (Start Recording)
3. Speak into the microphone
4. Verify text appears in the UI within chunk_duration + ~5 seconds
5. Click "停止" (Stop) to end recording
6. Check output file in `output/transcript_YYYYMMDD_HHMMSS.txt`

## Architecture

### Threading Model (Critical)

The application uses a **3-thread architecture** for continuous recording:

1. **Recording Thread** (`audio/recorder.py:_recording_loop`)
   - Runs in `AudioRecorder.recording_thread`
   - Continuously reads from PyAudio stream in a tight loop
   - Pushes raw audio data to buffer manager
   - Never blocks on API calls

2. **Chunk Processing Thread** (`audio/buffer.py:_process_chunks`)
   - Runs in `AudioBufferManager.processing_thread`
   - Monitors a queue for ready chunks (30s/60s of audio)
   - Calls `on_chunk_ready` callback when chunk is complete
   - Handles chunk-to-API handoff

3. **Main/GUI Thread** (`gui/main_window.py`)
   - Runs customtkinter event loop
   - Updates UI with transcription results
   - Manages file I/O for saving transcripts

**Key Design**: Recording never stops for API calls. Buffer manager accumulates data and splits into chunks asynchronously.

### Data Flow

```
Microphone → PyAudio → Recording Thread → AudioBufferManager.buffer
                                              ↓ (every 30s/60s)
                                         chunk_queue
                                              ↓
                                    Processing Thread
                                              ↓
                                    on_chunk_ready callback
                                              ↓
                          TranscriptionManager (in MainWindow)
                                              ↓
                          API Client (Whisper/GPT-4o)
                                              ↓
                          GUI Update + File Save
```

### Configuration System

Settings are loaded from **two sources** (both required):

1. **`config/default.yaml`** - Application settings
   - Audio parameters (sample rate, channels, format)
   - Transcription settings (chunk duration, model selection, language)
   - Output settings (directory, format, auto-save)
   - UI settings (language, theme)

2. **`.env`** - API Keys (Git-ignored)
   - `OPENAI_API_KEY` - For gpt-4o-transcribe / gpt-4o-transcribe-diarize
   - `GROQ_API_KEY` - For Whisper Large V3 Turbo

Settings are loaded in `src/config/settings.py` using a singleton pattern (`get_settings()`).

### Transcription Models

Three models supported via `transcription.model` setting:

- `whisper-groq` - Groq API, fast, free tier available (default)
- `gpt-4o-transcribe` - OpenAI API, higher accuracy
- `gpt-4o-diarize` - OpenAI API, includes speaker labels ([話者A], [話者B])

Model selection is in `src/gui/main_window.py:_create_transcriber()`.

## Critical Implementation Details

### Audio Format Requirements

**Always use 16kHz mono for Whisper compatibility**:
- Sample rate: 16000 Hz (Whisper's native rate)
- Channels: 1 (mono)
- Format: 16-bit PCM (`pyaudio.paInt16`)

These are configured in `config/default.yaml` under `audio:`.

### Chunk Duration Calculation

Chunk size in bytes = `2 * sample_rate * channels * chunk_duration_sec`

Example for 30s chunks:
```
2 bytes (16-bit) * 16000 Hz * 1 channel * 30s = 960,000 bytes
```

This calculation is in `AudioBufferManager.__init__` (src/audio/buffer.py:44).

### API Client Error Handling

Both Whisper and GPT-4o clients implement:
- Exponential backoff on rate limits (429 errors): wait = 2^attempt seconds
- Max 3 retries (`max_retries` parameter)
- Graceful degradation: return `None` on failure (doesn't crash app)

See `src/transcription/whisper_client.py:73-128` and `src/transcription/gpt4o_client.py:72-139`.

### Speaker Diarization Format

When using `gpt-4o-transcribe-diarize` model:
- API returns `response_format="diarized_json"` with segments
- Each segment has: `speaker`, `start`, `end`, `text`
- Format output as: `[HH:MM:SS] [話者A] text`
- Speaker mapping: SPEAKER_0 → 話者A, SPEAKER_1 → 話者B, etc.

Implementation in `src/transcription/gpt4o_client.py:_format_diarized_response`.

## Development Workflow

### Git Commit Convention

Follow this pattern from `PROMPT.md`:

```
[Phase X] TaskName: Brief description

Examples:
[Phase 1] 録音モジュール: 基本録音機能を実装
[Phase 2] 多言語対応: 日本語/中国語切り替え機能を実装
[Fix] VAD: 無音検出の感度調整
```

Always check `進捗.md` before starting work to understand current phase and completed tasks.

### Adding New Features

When adding features:
1. Read `PROMPT.md` for detailed requirements and specifications
2. Check `進捗.md` for phase assignments and task status
3. Update configuration in `config/default.yaml` if needed
4. Update `進捗.md` when completing tasks
5. Follow the existing threading model (no blocking in recording thread)

### Common Gotchas

1. **PyAudio Installation on Windows**
   - May require Visual C++ Build Tools
   - Alternative: Download wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

2. **API Rate Limits**
   - Groq Whisper: 2 hours/hour free tier
   - Handle rate limits gracefully (already implemented with backoff)

3. **Memory Management**
   - Buffer manager clears processed chunks automatically
   - Queue has maxsize=100 to prevent unbounded growth
   - Old chunks dropped if queue full (see `buffer.py:89-95`)

4. **Thread Safety**
   - AudioBufferManager.buffer uses `buffer_lock` for thread-safe access
   - Chunk queue is thread-safe (queue.Queue)
   - Don't share state between threads without locks

## Phase 2 Features (Completed)

- **VAD (Voice Activity Detection)**: webrtcvad-based silence detection to skip API calls on silent chunks, reducing costs
  - Configurable aggressiveness (0-3)
  - Automatic speech detection with 30% threshold
  - See `src/audio/vad.py` and integration in `src/audio/buffer.py`

- **Multilingual UI**: Japanese/Chinese language toggle
  - Language resources in `src/locales/{ja,zh}.json`
  - Locale manager in `src/locales/locale_manager.py`
  - Language button in title bar switches between ja ⇄ zh
  - All UI elements localized

- **Settings Dialog**: Full configuration UI (src/gui/settings_dialog.py)
  - Chunk duration (30s/60s)
  - API model selection (whisper-groq, gpt-4o-transcribe, gpt-4o-diarize)
  - Transcription language (ja/zh/en)
  - VAD enable/disable and sensitivity
  - Output format (txt/md/json)

- **Multiple Output Formats**:
  - **txt**: Simple text with header
  - **md**: Markdown with metadata (date, duration, model)
  - **json**: Full JSON with metadata and per-chunk details
  - See `src/utils/output_formatter.py`

## Phase 3+ Roadmap (Optional)

- Memory optimization
- Accuracy improvements (prompt tuning, chunk overlap)
- Hotkey support
- Enhanced multi-speaker support

## File Structure Reference

```
src/
├── main.py                      # Entry point - initializes settings, logger, GUI
├── audio/
│   ├── recorder.py              # PyAudio recording loop (separate thread)
│   └── buffer.py                # Chunk splitting and queue management
├── transcription/
│   ├── whisper_client.py        # Groq Whisper API client
│   └── gpt4o_client.py          # OpenAI GPT-4o Audio API client
├── config/
│   └── settings.py              # YAML config + .env loader (singleton)
├── gui/
│   └── main_window.py           # customtkinter UI + transcription orchestration
└── utils/
    └── logger.py                # loguru-based logging with rotation

config/default.yaml              # Application configuration
.env                             # API keys (Git-ignored, copy from .env.example)
進捗.md                          # Development progress tracking (in Japanese)
PROMPT.md                        # Detailed requirements and specs (in Japanese)
```

## Important Notes

- The UI supports Japanese and Chinese with a toggle button in the title bar.
- All API calls are synchronous. Async support exists in client code but not used yet.
- Auto-save is always enabled (`output.auto_save: true`).
- VAD is implemented and can be enabled via settings dialog (`vad.enabled` in config).
- Text output format changed: timestamps removed, continuous text output (no line breaks between chunks).
- PCM audio data is converted to WAV format before API submission (using Python's `wave` module).
