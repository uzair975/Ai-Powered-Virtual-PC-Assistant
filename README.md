# JARVIS AI Assistant

![Python](https://img.shields.io/badge/Python-3.12-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6-orange)
![Speech](https://img.shields.io/badge/STT-Faster--Whisper-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

JARVIS AI Assistant is a desktop voice assistant with a polished PySide6 interface, real-time speech recognition, text-to-speech feedback, command execution, webcam display, and gesture-based virtual mouse control. It is designed as a final-year project style assistant that combines a modern desktop frontend with practical automation features.

## Highlights

- Voice command pipeline with Silero VAD and Faster-Whisper speech recognition
- Text-to-speech responses using `pyttsx3`
- Groq LLM integration for conversational fallback and query handling
- Professional PySide6 desktop UI with animated AI core visualization
- Live webcam panel with threaded frame capture
- Conversation panel with typing animation and command history
- Wake-word detection with fuzzy matching for common STT variations of "Jarvis"
- Windows system controls for apps, websites, volume, brightness, lock, shutdown, restart, screenshots, and more
- Gesture control mode for virtual mouse interaction using webcam hand tracking
- Demo mode for testing the interface without the full voice backend

## Demo And Run Modes

### Full Integrated App

Runs the UI with the real speech, TTS, command processor, and gesture handoff pipeline.

```powershell
python run_integrated.py --mode real
```

### UI Demo Mode

Runs the desktop interface without initializing the real STT/TTS backend.

```powershell
python run_integrated.py --mode demo
```

To auto-generate sample commands:

```powershell
python run_integrated.py --mode demo --auto-demo
```

### Standalone Frontend

Runs only the PySide6 frontend.

```powershell
python ui_main.py
```

### Console Voice Assistant

Runs the non-GUI voice assistant loop.

```powershell
python main.py
```

### Standalone Gesture Agent

Runs hand-tracking gesture control directly.

```powershell
python gesture.py
```

## Project Structure

```text
.
|-- run_integrated.py          # Main integrated PySide6 + voice assistant launcher
|-- main.py                    # Console voice assistant orchestrator
|-- command_processor.py       # Intent detection, system commands, web actions, LLM fallback
|-- stt_module.py              # Silero VAD + Faster-Whisper speech-to-text engine
|-- tts_module.py              # pyttsx3 text-to-speech wrapper
|-- gesture.py                 # Gesture-based virtual mouse controller
|-- handtracking.py            # MediaPipe hand tracking helpers
|-- ui_main.py                 # Main frontend window
|-- demo_app.py                # UI demo application
|-- requirements.txt           # Python dependencies
|-- QUICKSTART.md              # Quick setup notes
|-- FRONTEND_GUIDE.md          # Frontend architecture guide
|-- PROJECT_SUMMARY.md         # Existing project summary
`-- ui_components/
    |-- backend_connector.py   # Threaded backend/UI signal bridge
    |-- brain_animation.py     # Animated AI core visualization
    |-- camera_panel.py        # Webcam display panel
    |-- conversation_panel.py  # Chat-style conversation UI
    |-- history_window.py      # Command history popup
    |-- left_panel.py          # Left-side UI layout
    |-- right_panel.py         # Right-side UI layout
    `-- styles.py              # Application theme
```
## Screenshots

### Main Interface

![Main Interface](assets/screenshots/main-ui.png)

### Demo Mode

![Demo Mode](assets/screenshots/demo-mode.png)

### Gesture Control

![Gesture Control](assets/screenshots/gesture-control.png)


## Requirements

- Python 3.12 recommended
- Windows 10/11 recommended for system automation features
- Working microphone
- Webcam for camera preview and gesture control
- Internet connection for Groq API calls and first-time model downloads
- Groq API key for LLM-powered responses

Some UI-only features can run on other platforms, but several command actions such as brightness, media keys, Office app launching, and lock/shutdown behavior are Windows-oriented.

## Installation

1. Clone the repository:

```powershell
git clone https://github.com/uzair975/Ai-Powered-Virtual-PC-Assistant
```

2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

5. Set your Groq API key:

```powershell
$env:GROQ_API_KEY="your_groq_api_key_here"
```

For a persistent Windows user environment variable:

```powershell
[Environment]::SetEnvironmentVariable("GROQ_API_KEY", "your_groq_api_key_here", "User")
```

Restart your terminal after setting a persistent variable.

## Configuration

Core runtime settings are in `main.py` under the `CONFIG` dictionary:

```python
CONFIG = {
    "WAKE_WORD": "jarvis",
    "WHISPER_MODEL": "tiny",
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
    "GROQ_MODEL": "llama-3.1-8b-instant",
    "TTS_RATE": 190,
    "TTS_VOLUME": 1.0,
    "VOICE_CONFIDENCE_THRESHOLD": 0.85,
}
```

Recommended changes:

- Use a larger Whisper model for better accuracy if your system can handle it.
- Adjust `VOICE_CONFIDENCE_THRESHOLD` if commands are being rejected too often.
- Tune `TTS_RATE` and `TTS_VOLUME` for your preferred speaking style.
- Keep API keys in environment variables, never in committed source code.

## Example Commands

Try commands such as:

```text
Jarvis open Google
Jarvis open Notepad
Jarvis search Python decorators
Jarvis increase volume
Jarvis decrease brightness
Jarvis take screenshot
Jarvis lock screen
Jarvis start gesture control
Jarvis go offline
```

The command processor supports exact keyword matching, fuzzy wake-word matching, direct website/app opening, and LLM fallback for general questions.

## Architecture

The project is split into four main layers:

```text
PySide6 UI
  -> signal bridge and worker threads
  -> STT, TTS, command processor
  -> system automation, web actions, LLM calls, gesture process
```

The frontend remains responsive by pushing camera capture, voice processing, and command execution into worker threads or background processes. UI updates are routed back through Qt signals.

## Key Components

| Component | Purpose |
| --- | --- |
| `run_integrated.py` | Main desktop application with real/demo mode selection |
| `VoiceAssistantBridge` | Connects voice backend events to the PySide6 UI |
| `STTEngine` | Records speech using VAD and transcribes with Faster-Whisper |
| `TTSEngine` | Speaks assistant responses using pyttsx3 |
| `CommandProcessor` | Classifies commands and executes supported actions |
| `CameraPanel` | Displays webcam feed without blocking the UI |
| `ConversationPanel` | Renders user/assistant/system messages |
| `gesture.py` | Provides webcam-based gesture control |

## Security Note

Before uploading this project publicly:

- Make sure no real API keys are committed.
- Rotate any API key that was previously committed or shared.
- Keep `GROQ_API_KEY` in your environment or a local secrets manager.
- Add local-only files such as `.venv/`, `__pycache__/`, logs, and model caches to `.gitignore`.

## Troubleshooting

### Backend falls back to demo mode

Check that all dependencies are installed and that `GROQ_API_KEY` is available in the active terminal.

```powershell
echo $env:GROQ_API_KEY
```

### Microphone does not work

Confirm your microphone is connected, selected as the default input device, and allowed in Windows privacy settings.

### Webcam is black or unavailable

Close other applications using the camera, then test OpenCV access:

```powershell
python -c "import cv2; c=cv2.VideoCapture(0); print(c.isOpened())"
```

### Faster-Whisper or Torch install issues

Use a clean Python 3.12 virtual environment and reinstall dependencies. If your system has a GPU-specific Torch setup, install the appropriate Torch build before installing the rest of the requirements.

### Brightness or volume commands do not work

These controls depend on Windows APIs, keyboard media keys, and display driver support. External monitors may not expose brightness control through the same interface as laptop displays.

## Documentation

- `QUICKSTART.md` - quick usage guide
- `FRONTEND_GUIDE.md` - frontend component and architecture reference
- `PROJECT_SUMMARY.md` - project summary and implementation notes

## Roadmap

- Add a settings panel for model, voice, and UI preferences
- Add persistent conversation and command history storage
- Add installer or packaged executable builds
- Add tests for intent classification and command routing
- Add screenshots or a short demo GIF for the GitHub repository

## License

No license file is currently included. Add a license before publishing if you want others to use, modify, or distribute the project.

## Acknowledgements

This project uses PySide6, OpenCV, MediaPipe, Faster-Whisper, Silero VAD, pyttsx3, Groq, and related Python automation libraries.
