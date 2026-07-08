#!/usr/bin/env python3

import sys
import threading
import time
import argparse
import os
import subprocess
import traceback
from queue import Queue


try:
    import torch  # noqa: F401
except Exception:
    for module_name in list(sys.modules):
        if module_name == "torch" or module_name.startswith("torch."):
            sys.modules.pop(module_name, None)
    # Let STTEngine surface the real error later if torch is genuinely broken.
    pass

try:
    from pynput import keyboard as _pynput_keyboard  # noqa: F401
except Exception:
    for module_name in list(sys.modules):
        if module_name == "pynput" or module_name.startswith("pynput."):
            sys.modules.pop(module_name, None)
    # CommandProcessor will report if keyboard controls are unavailable.
    pass

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Signal, QObject

# Import UI components
from ui_main import MainWindow
from ui_components.backend_connector import BackendConnector

# Import voice assistant components
# Uncomment these when integrating with real backend
# from main import CONFIG
# from stt_module import STTEngine
# from tts_module import TTSEngine
# from command_processor import CommandProcessor


class VoiceAssistantBridge(QObject):
    """
    Bridge between voice assistant and UI
    Converts between voice assistant signals and Qt signals
    """
    
    # Signals to UI
    command_recognized_signal = Signal(str, float)  # command, confidence
    response_ready_signal = Signal(str)  # response text
    status_changed_signal = Signal(str, str)  # status, message
    
    def __init__(self, stt_engine=None, tts_engine=None, processor=None):
        super().__init__()
        
        self.stt_engine = stt_engine
        self.tts_engine = tts_engine
        self.processor = processor
        self.auto_speak_responses = bool(stt_engine and tts_engine and processor)
        
        # Internal state
        self.is_listening = False
        self.command_queue = Queue()
        self._tts_lock = threading.Lock()
        self._tts_active = threading.Event()
        
        # Processing thread
        self.processing_thread = threading.Thread(target=self._process_voice_loop, daemon=True)
        self.processing_thread.start()
    
    def _process_voice_loop(self):
        """
        Main voice processing loop (runs in background thread)
        Simulates: Listen â†’ Recognize â†’ Process â†’ Respond
        """
        print("[BRIDGE] Voice assistant bridge started")
        
        while True:
            try:
                if not self.is_listening or self._tts_active.is_set():
                    time.sleep(0.1)
                    continue

                # Real backend path: pull audio text from STT and process it.
                if self.stt_engine and self.processor:
                    text = None
                    confidence = 0.85

                    if hasattr(self.stt_engine, "listen_blocking"):
                        result = self.stt_engine.listen_blocking()
                    elif hasattr(self.stt_engine, "listen"):
                        result = self.stt_engine.listen()
                    else:
                        self.status_changed_signal.emit(
                            "ERROR",
                            "STT engine missing listen/listen_blocking method",
                        )
                        time.sleep(0.5)
                        continue

                    if isinstance(result, tuple):
                        if len(result) >= 1:
                            text = result[0]
                        if len(result) >= 2 and isinstance(result[1], (int, float)):
                            confidence = float(result[1])
                    elif isinstance(result, str):
                        text = result

                    if not text:
                        continue

                    response = self.processor.process(text)
                    if response:
                        response_text = str(response)
                        if response_text == "QUIT_AGENT":
                            self.is_listening = False
                        self.command_recognized_signal.emit(text, confidence)
                        self.response_ready_signal.emit(response_text)

                        # In real backend mode, speak in this same worker thread so
                        # listening does not restart while TTS is playing.
                        if self.auto_speak_responses and response_text not in {"QUIT_AGENT", "LAUNCH_GESTURE"}:
                            self.handle_tts_response(response_text)
                else:
                    # Demo/non-integrated path: idle until simulate_command is called.
                    time.sleep(0.1)
                
            except Exception as e:
                print(f"[BRIDGE ERROR] {e}")
                self.status_changed_signal.emit("ERROR", str(e))
                time.sleep(0.2)
    
    def start_listening(self):
        """Start voice recognition"""
        print("[BRIDGE] Starting voice recognition...")
        self.is_listening = True
        self.status_changed_signal.emit("LISTENING", "Microphone active")
    
    def stop_listening(self):
        """Stop voice recognition"""
        print("[BRIDGE] Stopping voice recognition...")
        self.is_listening = False
        self.status_changed_signal.emit("IDLE", "Waiting for voice input")
    
    def simulate_command(self, command: str, confidence: float = 0.85):
        """
        Simulate voice command detection
        Use this for testing without real STT
        """
        print(f"[BRIDGE] Simulated command: {command}")

        # Simulate processing
        if self.processor:
            try:
                response = self.processor.process(command)
                if response:
                    if str(response) == "QUIT_AGENT":
                        self.is_listening = False
                    self.command_recognized_signal.emit(command, confidence)
                    self.response_ready_signal.emit(response)
            except Exception as e:
                self.status_changed_signal.emit("ERROR", str(e))
    
    def handle_tts_response(self, text: str):
        """Handle TTS output"""
        if not self.tts_engine:
            return
        if not text or not str(text).strip():
            return

        with self._tts_lock:
            self._tts_active.set()
            try:
                if hasattr(self.tts_engine, "speak_sync"):
                    self.tts_engine.speak_sync(text)
                else:
                    self.tts_engine.speak(text)
            except Exception as e:
                print(f"[TTS ERROR] {e}")
            finally:
                self._tts_active.clear()
                if self.is_listening:
                    self.status_changed_signal.emit("LISTENING", "Microphone active")
                else:
                    self.status_changed_signal.emit("IDLE", "Waiting for voice input")


class JarvisApplication(MainWindow):
    """
    Main application window with voice assistant integration
    Combines UI frontend with voice backend
    """
    
    def __init__(self, use_real_backend=False, auto_demo=False):
        super().__init__()
        
        self.use_real_backend = use_real_backend
        self.auto_demo = auto_demo
        self.gesture_process = None
        self.gesture_monitor_timer = QTimer(self)
        self.gesture_monitor_timer.setInterval(750)
        self.gesture_monitor_timer.timeout.connect(self._check_gesture_process)
        
        # Initialize based on mode
        if use_real_backend:
            self._init_real_backend()
        else:
            self._init_demo_backend()
    
    def _init_demo_backend(self):
        """Initialize with demo backend (no real STT/TTS)"""
        print("[APP] Running in DEMO MODE")
        
        # Create bridge without real engines
        self.bridge = VoiceAssistantBridge()
        
        # Connect bridge signals to UI
        self.bridge.command_recognized_signal.connect(self._on_command_recognized)
        self.bridge.response_ready_signal.connect(self._on_response_ready)
        self.bridge.status_changed_signal.connect(self._on_status_changed)
        
        self._play_startup_greeting()
        
        # Start listening
        self.bridge.start_listening()
        
        if self.auto_demo:
            # Add demo commands every 5 seconds
            self.demo_timer = QTimer()
            self.demo_timer.timeout.connect(self._run_demo_command)
            self.demo_timer.start(5000)
            self.right_panel.add_system_message(
                "DEMO MODE: Auto-simulating sample commands."
            )
        else:
            self.right_panel.add_system_message(
                "DEMO MODE: No auto commands. Use REAL mode for execution."
            )
    
    def _init_real_backend(self):
        """Initialize with real voice assistant backend"""
        print("[APP] Initializing REAL BACKEND")
        
        try:
            # Import voice assistant modules
            from main import CONFIG
            from stt_module import STTEngine
            from tts_module import TTSEngine
            from command_processor import CommandProcessor
            
            # Initialize engines
            print("[APP] Loading STT Engine...")
            stt_engine = STTEngine(whisper_model=CONFIG["WHISPER_MODEL"])
            
            print("[APP] Loading TTS Engine...")
            tts_engine = TTSEngine(rate=CONFIG["TTS_RATE"], volume=CONFIG["TTS_VOLUME"])
            
            print("[APP] Loading Command Processor...")
            processor = CommandProcessor(
                groq_api_key=CONFIG["GROQ_API_KEY"],
                groq_model=CONFIG["GROQ_MODEL"]
            )
            # Let frontend manage camera handoff and gesture process lifecycle.
            processor.manage_gesture_externally = True
            
            # Create bridge
            self.bridge = VoiceAssistantBridge(stt_engine, tts_engine, processor)
            
            # Connect signals
            self.bridge.command_recognized_signal.connect(self._on_command_recognized)
            self.bridge.response_ready_signal.connect(self._on_response_ready)
            self.bridge.status_changed_signal.connect(self._on_status_changed)
            
            self._play_startup_greeting()

            # Start listening after greeting so the mic does not capture
            # Jarvis's own startup line.
            self.bridge.start_listening()
            
            self.right_panel.add_system_message("Voice assistant initialized. Listening...")
            
        except Exception as e:
            print(f"[ERROR] Backend initialization failed: {e}")
            traceback.print_exc()
            self.right_panel.add_system_message(f"Backend initialization failed: {e}")
            self._init_demo_backend()  # Fall back to demo

    def _play_startup_greeting(self):
        """Play startup greeting."""
        greeting = "Jarvis is at your service, tell me what can I do."
        self.bridge.handle_tts_response(greeting)
    
    def _run_demo_command(self):
        """Run demo command"""
        demo_commands = [
            ("Jarvis open Google", 0.95),
            ("What time is it", 0.90),
            ("Increase brightness", 0.92),
            ("Play some music", 0.88),
            ("Set a reminder for 5 PM", 0.85),
        ]
        
        import random
        command, confidence = random.choice(demo_commands)
        self.bridge.simulate_command(command, confidence)
    
    def _on_command_recognized(self, command: str, confidence: float):
        """Handle recognized command"""
        print(f"[UI] Command: {command} ({confidence:.0%})")
        
        # Display in UI
        self.right_panel.add_user_command(command)
        self.left_panel.add_history_entry(command)
        
        # Update status
        self.right_panel.add_system_message(f"Processing: {command}")
    
    def _on_response_ready(self, response: str):
        """Handle assistant response"""
        print(f"[UI] Response: {response}")

        if response == "LAUNCH_GESTURE":
            self._launch_gesture_with_camera_handoff()
            return

        if response == "QUIT_AGENT":
            final_message = "Going offline."
            self.right_panel.add_assistant_response(final_message, animate=True)
            self.bridge.handle_tts_response(final_message)
            self.bridge.stop_listening()
            QTimer.singleShot(300, self.close)
            return
        
        # Display response with typing animation
        self.right_panel.add_assistant_response(response, animate=True)
        
        # In real backend mode bridge handles speech in the worker thread to
        # avoid feedback loops. Keep UI-triggered TTS for demo/manual paths.
        if not getattr(self.bridge, "auto_speak_responses", False):
            self.bridge.handle_tts_response(response)
        
        # Update status
        self.right_panel.add_system_message("Response complete")
    
    def _on_status_changed(self, status: str, message: str):
        """Handle status updates"""
        print(f"[STATUS] {status}: {message}")
        
        if status not in ["LISTENING", "IDLE"]:
            self.right_panel.add_system_message(f"{status}: {message}")

    def _launch_gesture_with_camera_handoff(self):
        """Release frontend camera, launch gesture process, then monitor until it exits."""
        if self.gesture_process and self.gesture_process.poll() is None:
            self.right_panel.add_assistant_response("Gesture control is already running.", animate=True)
            return

        self.right_panel.add_system_message("Releasing camera for gesture control...")
        self.right_panel.camera_panel.pause_camera()
        QTimer.singleShot(500, self._start_gesture_process)

    def _start_gesture_process(self):
        """Start external gesture process after camera handoff."""
        gesture_script = os.path.join(os.path.dirname(__file__), "gesture.py")
        if not os.path.exists(gesture_script):
            self.right_panel.add_assistant_response("gesture.py not found.", animate=True)
            self.right_panel.camera_panel.resume_camera()
            return

        try:
            self.gesture_process = subprocess.Popen([sys.executable, gesture_script])
            self.right_panel.add_assistant_response("Gesture agent launched.", animate=True)
            self.bridge.handle_tts_response("Gesture agent launched.")
            if not self.gesture_monitor_timer.isActive():
                self.gesture_monitor_timer.start()
        except Exception as e:
            self.right_panel.add_assistant_response("Failed to launch gesture agent.", animate=True)
            self.right_panel.add_system_message(f"Gesture launch error: {e}")
            self.right_panel.camera_panel.resume_camera()

    def _check_gesture_process(self):
        """Restore frontend camera when gesture process exits."""
        if not self.gesture_process:
            self.gesture_monitor_timer.stop()
            return
        if self.gesture_process.poll() is None:
            return

        self.gesture_monitor_timer.stop()
        self.gesture_process = None
        self.right_panel.camera_panel.resume_camera()
        self.right_panel.add_system_message("Gesture control closed. Camera resumed.")
    
    def closeEvent(self, event):
        """Cleanup on close"""
        if hasattr(self, 'demo_timer'):
            self.demo_timer.stop()
        if self.gesture_monitor_timer.isActive():
            self.gesture_monitor_timer.stop()
        if self.gesture_process and self.gesture_process.poll() is None:
            try:
                self.gesture_process.terminate()
            except Exception:
                pass
        
        if getattr(self.bridge, "is_listening", False):
            self.bridge.stop_listening()
        super().closeEvent(event)


def main():
    """Application entry point"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["demo", "real"],
        default="real",
        help="Run with demo simulation or real backend.",
    )
    parser.add_argument(
        "--auto-demo",
        action="store_true",
        help="In demo mode, auto-generate sample commands every 5 seconds.",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    
    mode = args.mode
    
    print("\n" + "="*60)
    print("JARVIS - AI Assistant Frontend + Backend")
    print("="*60)
    print(f"Mode: {mode.upper()}\n")
    
    window = JarvisApplication(
        use_real_backend=(mode == "real"),
        auto_demo=args.auto_demo,
    )
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
