#!/usr/bin/env python3
"""
Text-to-Speech Module
- Fresh engine instance for every utterance
- Keeps execution reliable on Windows Python environments
"""

import threading
import pyttsx3


class TTSEngine:
    def __init__(self, rate=190, volume=1.0):
        """Initialize TTS engine."""
        self.rate = rate
        self.volume = volume
        self.is_ready = True
        print("[TTS] Ready - fresh engine per utterance mode")

    def speak(self, text, show_log=True):
        """Speak text in a short-lived worker thread."""
        if not text or not text.strip():
            return

        if show_log:
            print(f"[ASSISTANT] {text}")

        def _speak_thread():
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                print(f"[TTS ERROR] {e}")

        thread = threading.Thread(target=_speak_thread, daemon=True)
        thread.start()
        thread.join(timeout=10)

    def speak_sync(self, text, show_log=True):
        """Synchronous version that blocks until speech finishes."""
        if not text or not text.strip():
            return

        if show_log:
            print(f"[ASSISTANT] {text}")

        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[TTS ERROR] {e}")

    def cleanup(self):
        """No persistent resources to clean up."""
        print("[TTS] Cleanup complete")

    # Stub methods for compatibility
    def set_rate(self, rate):
        self.rate = rate

    def set_volume(self, volume):
        self.volume = volume

    def stop(self):
        pass

    def is_speaking(self):
        return False

    def wait_until_done(self, timeout=None):
        pass
