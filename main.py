#!/usr/bin/env python3
"""
Main Voice Assistant Orchestrator - FIXED WAKE WORD VERSION
- Fuzzy matching for wake word detection (catches jardis, jarves, etc.)
- Silero VAD for intelligent listening
- Faster-Whisper for STT
- Fresh TTS engine per utterance
"""
import time
import queue
import threading
import sys
import os

# Import modules
from stt_module import STTEngine
from tts_module import TTSEngine
from command_processor import CommandProcessor

# ============= CONFIGURATION =============
CONFIG = {
    # Voice settings
    "WAKE_WORD": "jarvis",
    "WHISPER_MODEL": "tiny",  # Using tiny for fastest response on your i5
    
    # LLM settings
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
    "GROQ_MODEL": "llama-3.1-8b-instant",
    
    # TTS settings
    "TTS_RATE": 190,
    "TTS_VOLUME": 1.0,
    
    # Confidence thresholds
    "VOICE_CONFIDENCE_THRESHOLD": 0.85,
}

# ============= GLOBAL STATE =============
class VoiceAssistant:
    def __init__(self, config):
        self.config = config
        self.running = True
        
        # Initialize modules
        print("[INIT] Initializing Voice Assistant...")
        print()
        
        try:
            # Speech-to-Text
            self.stt = STTEngine(
                whisper_model=config["WHISPER_MODEL"]
            )
            print("[INIT] ✓ STT Engine initialized (VAD: intelligent listening)")
            
            # Text-to-Speech
            self.tts = TTSEngine(
                rate=config["TTS_RATE"],
                volume=config["TTS_VOLUME"]
            )
            print("[INIT] ✓ TTS Engine initialized")
            
            # Command Processor with improved wake word detection
            self.processor = CommandProcessor(
                groq_api_key=config["GROQ_API_KEY"],
                groq_model=config["GROQ_MODEL"]
            )
            print("[INIT] ✓ Command Processor initialized (fuzzy wake word matching)")
            
        except Exception as e:
            print(f"[ERROR] Initialization failed: {e}")
            raise
        
        # State tracking
        self.q_voice = queue.Queue()
        self.q_text = queue.Queue()
    
    def listen_mic_continuous(self):
        """
        Continuous microphone listening thread.
        Uses VAD - waits for speech, stops when you stop speaking
        """
        print(f"[MIC] Started voice listening thread (intelligent VAD active)\n")
        
        while self.running:
            text, confidence = self.stt.listen_blocking()
            
            if text:
                print(f"[VOICE] {text} (confidence: {confidence:.2f})")
                
                # Filter by confidence threshold
                if confidence >= self.config["VOICE_CONFIDENCE_THRESHOLD"]:
                    self.q_voice.put(text)
                    print(f"[ACCEPT] Confidence {confidence:.2f} >= threshold {self.config['VOICE_CONFIDENCE_THRESHOLD']}\n")
                else:
                    print(f"[REJECT] Confidence {confidence:.2f} below threshold {self.config['VOICE_CONFIDENCE_THRESHOLD']}\n")
            else:
                # No speech detected, just continue listening
                time.sleep(0.1)
    
    def listen_keyboard(self):
        """
        Keyboard input thread for manual text commands.
        """
        print("[KEYBOARD] Ready for text input (type commands or 'exit' to quit)\n")
        
        while self.running:
            try:
                user_input = input()
                
                if user_input.strip().lower() == "exit":
                    print("[SYSTEM] Exiting...")
                    self.running = False
                    break
                
                if user_input.strip():
                    print(f"[TEXT] {user_input}")
                    self.q_text.put(user_input)
            
            except (EOFError, KeyboardInterrupt):
                print("[SYSTEM] Keyboard input ended")
                break
            except Exception as e:
                print(f"[ERROR] Keyboard input error: {e}")
    
    def handle_voice_input(self, text):
        """Process voice input directly"""
        return text.strip()
    
    def handle_text_input(self, text):
        """Process keyboard input directly"""
        return text.strip()
    
    def run_main_loop(self):
        """Main event loop"""
        print("\n" + "="*70)
        print(f"🎤 Voice Assistant Ready")
        print(f"   Listening mode: Intelligent VAD (stops when you stop speaking)")
        print(f"   Confidence threshold: {self.config['VOICE_CONFIDENCE_THRESHOLD']}")
        print(f"   Wake word: '{self.config['WAKE_WORD']}' (fuzzy matching: accepts similar variations)")
        print(f"   Say: 'quit' or 'offline' to stop")
        print("="*70 + "\n")
        
        # Start listening threads
        mic_thread = threading.Thread(target=self.listen_mic_continuous, daemon=True)
        keyboard_thread = threading.Thread(target=self.listen_keyboard, daemon=True)
        
        mic_thread.start()
        keyboard_thread.start()
        
        # Main event loop
        try:
            while self.running:
                # Check keyboard input (priority)
                if not self.q_text.empty():
                    user_text = self.q_text.get()
                    command = self.handle_text_input(user_text)
                    
                    if command:
                        print(f"[PROCESS] Keyboard: {command}")
                        response = self.processor.process(command, self.config["WAKE_WORD"])
                        
                        # Handle None response (wake word not detected)
                        if response is None:
                            print(f"[SYSTEM] Command ignored (no valid wake word)\n")
                            continue
                        
                        # Check if user wants to quit
                        if response == "QUIT_AGENT":
                            print("[SYSTEM] Shutting down...")
                            self.tts.speak("Goodbye!")
                            self.running = False
                            break
                        
                        self.tts.speak(response)
                    
                    continue
                
                # Check voice input
                if not self.q_voice.empty():
                    user_text = self.q_voice.get()
                    command = self.handle_voice_input(user_text)
                    
                    if command:
                        print(f"[PROCESS] Voice: {command}")
                        response = self.processor.process(command, self.config["WAKE_WORD"])
                        
                        # Handle None response (wake word not detected)
                        if response is None:
                            print(f"[FILTER] 🚫 No wake word detected\n")
                            continue
                        
                        # Check if user wants to quit
                        if response == "QUIT_AGENT":
                            print("[SYSTEM] Shutting down...")
                            self.tts.speak("Goodbye!")
                            self.running = False
                            break
                        
                        self.tts.speak(response)
                    
                    continue
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n[SYSTEM] Interrupted by user")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        print("[CLEANUP] Shutting down...")
        self.running = False
        
        try:
            self.stt.cleanup()
            self.tts.cleanup()
            print("[CLEANUP] ✓ All resources released")
        except Exception as e:
            print(f"[CLEANUP] Error: {e}")

# ============= ENTRY POINT =============
if __name__ == "__main__":
    try:
        assistant = VoiceAssistant(CONFIG)
        assistant.run_main_loop()
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)
