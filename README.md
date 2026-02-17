# LocalVoice

A lightweight, cross-platform desktop utility for offline voice-to-text transcription. LocalVoice sits as a small floating window, allowing you to dictate text that gets automatically inserted into any application.

**Key Feature:** 100% offline operation ensuring total privacy.

## Features

- **Push-to-Talk:** Click the microphone button or use global hotkeys
- **Global Hotkeys:** Record custom key combinations (e.g., `Ctrl+Shift`, `F10`, `Caps Lock`)
- **Two Activation Modes:**
  - **Hold:** Hold key(s) to record, release to stop
  - **Toggle:** Press once to start, press again to stop
- **Multi-Language Support:** Auto-detect or choose from 16+ languages
- **Flexible Text Injection:** Clipboard paste or keyboard simulation
- **System Tray:** Minimize to tray, quick access menu
- **GPU Acceleration:** Automatic CUDA detection for faster transcription

## Installation

### Requirements
- Python 3.10+
- PortAudio (for audio capture)

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd local-voice

# Install dependencies
pip install -r requirements.txt

# (Optional) Pre-download model for offline use
python download_models.py base

# Run the application
python -m src.main
```

### macOS Permissions

On macOS, you need to grant:
1. **Microphone access** - When prompted, allow LocalVoice to use the microphone
2. **Accessibility access** - System Preferences → Privacy & Security → Accessibility → Add Terminal/Python

## Usage

### Basic Operation

1. **Click the microphone** or **press your hotkey** to start recording
2. **Speak your text**
3. **Click again** or **release hotkey** (hold mode) to stop
4. Transcribed text is inserted at your cursor position

### Global Hotkeys

Configure hotkeys in Settings → Hotkey:
1. Click **Record**
2. Press your desired key combination
3. Choose **Hold** or **Toggle** mode
4. Click **OK** to save

**Examples:**
- `Caps Lock` (Hold) - Hold to record
- `F10` (Toggle) - Press to start/stop
- `Ctrl+Shift` (Hold) - Hold both to record
- `Alt+A` (Toggle) - Press combination to toggle

### Settings

| Tab | Options |
|-----|---------|
| **General** | Start minimized, language, window opacity |
| **Model** | Whisper model size, processing device (Auto/CPU/GPU) |
| **Hotkey** | Record custom hotkey, hold/toggle mode |
| **Injection** | Text insertion method, trailing space, clipboard preservation |

### Model Sizes

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| Tiny | 39MB | Fastest | Basic |
| Base | 74MB | Fast | Good |
| Small | 244MB | Medium | Better |
| Medium | 769M | Slow | High |
| Large v3 | 1550M | Slowest | Best |

## Project Structure

```
local-voice/
├── src/
│   ├── main.py              # Application entry point
│   ├── gui/
│   │   ├── main_window.py   # Floating window UI
│   │   ├── settings_dialog.py
│   │   └── tray_icon.py
│   ├── audio/
│   │   └── recorder.py      # Audio capture with SoundDevice
│   ├── transcription/
│   │   └── engine.py        # faster-whisper integration
│   ├── injection/
│   │   └── text_injector.py # Clipboard/keyboard injection
│   └── hotkey/
│       └── manager.py       # Global hotkey handling
├── config/
│   └── settings.json        # User preferences
├── download_models.py       # Pre-download models script
├── requirements.txt
└── pyproject.toml
```

## Technical Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| GUI Framework | PyQt6 |
| STT Engine | faster-whisper (Optimized OpenAI Whisper) |
| Audio Processing | SoundDevice |
| Global Hotkeys | pynput |
| Text Injection | pyperclip + pynput |
| Window Management | pywinctl |

## Configuration

Settings are stored in `config/settings.json`:

```json
{
    "model_size": "base",
    "language": "auto",
    "hotkey": "caps_lock",
    "hotkey_mode": "hold",
    "injection_method": "clipboard",
    "start_minimized": false,
    "window_opacity": 95,
    "device": "auto",
    "typing_delay": 10,
    "add_trailing_space": true,
    "preserve_clipboard": true
}
```

## Offline Operation

For fully offline use, pre-download the model:

```bash
# Download base model (recommended)
python download_models.py base

# Download multiple models
python download_models.py tiny base small

# Download all models
python download_models.py all
```

Models are stored in `~/.localvoice/models/`

## Troubleshooting

### Hotkey not working
- Ensure accessibility permissions are granted (macOS)
- Check if another app is using the same hotkey
- Try a different key combination

### No audio recorded
- Check microphone permissions
- Verify correct microphone is selected in system settings

### Slow transcription
- Use a smaller model (tiny or base)
- Enable GPU acceleration if available
- Close other resource-intensive applications

## License

MIT License
