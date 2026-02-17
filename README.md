# Project Specification: LocalVoice

## 1. Project Overview

**LocalVoice** is a lightweight, cross-platform desktop utility designed to streamline text entry through high-accuracy voice recognition. The application sits as a small, non-intrusive floating window that allows users to dictate text and have it automatically inserted into the active cursor position of any other application (Word, Browser, Terminal, etc.).

The defining feature of this project is its **100% offline operation**, ensuring total privacy and functionality without an internet connection.

---

## 2. Core Features

* **Push-to-Talk (PTT):** A toggleable microphone button in the UI.
* **Global Hotkey Support:** A configurable keyboard shortcut (e.g., holding `Caps Lock` or `F10`) to trigger recording without focusing the app.
* **Automatic Text Injection:** Real-time or post-processing insertion of transcribed text into the previously active window.
* **Multi-Platform Support:** Native-like performance on Windows, Linux, and macOS.
* **Local Inference:** High-speed Speech-to-Text (STT) processing using local hardware (CPU/GPU).

---

## 3. Technical Stack

| Component | Technology |
| --- | --- |
| **Language** | Python 3.10+ |
| **GUI Framework** | PyQt6 or PySide6 (Qt for Python) |
| **STT Engine** | `faster-whisper` (Optimized OpenAI Whisper) |
| **Audio Processing** | `PyAudio` or `SoundDevice` |
| **Input Simulation** | `pynput` (for global hotkeys and keyboard typing) |
| **Packaging** | `PyInstaller` or `Nuitka` (to bundle models and dependencies) |

---

## 4. Requirements

### 4.1 Functional Requirements

1. **Audio Capture:** The app must capture high-quality audio from the system's default microphone.
2. **Transcription Engine:**
* Must use a local model (e.g., Whisper "Base" or "Small"), configurable.
* Must support multiple languages.
* Must automatically handle punctuation and casing.


3. **Window Behavior:**
* The UI must have an "Always on Top" property.
* The window should be draggable and minimalist (Icon-centric).


4. **Text Insertion Logic:**
* The app must detect the "Last Active Window" before capturing focus.
* It should simulate keyboard events (typing) or use the system clipboard to paste text at the cursor location. Also configurable.



### 4.2 Non-Functional Requirements

1. **Privacy:** Zero data transmission to external servers. All audio processing happens in RAM/Local Disk.
2. **Performance:** Transcription latency should be minimal (less than 1 second for short sentences on modern hardware).
3. **Offline Capability:** The application must bundle all necessary AI weights/models so it works without a Wi-Fi connection. A installation script can be used if needed.
4. **Resource Management:** The app should sit idle with low CPU/RAM usage when not recording.

---

## 5. User Interface (UI) Design

* **Main View:** A small circular or rounded-square window.
* **States:**
* *Idle:* Gray/White microphone icon.
* *Recording:* Red glowing icon or pulse animation.
* *Processing:* Rotating loader or "thinking" icon.


* **Settings Menu:** Accessible via right-click to configure:
* Model size (Tiny/Base/Small).
* Preferred Hotkey.
* Use clipboard or keyboard events



---