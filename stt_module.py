#!/usr/bin/env python3
"""
Speech-to-Text Module with Silero VAD.
- Uses front-end VAD capture with pre-roll to avoid clipping first word.
- Faster-Whisper transcription.
- Lightweight false-positive filtering.
"""

import collections
import time

import numpy as np
import sounddevice as sd
import torch
from faster_whisper import WhisperModel


class SileroVAD:
    """Silero Voice Activity Detector - Pure Python wrapper."""

    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.trigger_level = 0.5
        self.frame_size = 512

        print("[VAD] Loading Silero VAD...")
        try:
            self.model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=True,
            )
            self.onnx_mode = False
            print("[VAD] OK Silero VAD loaded")
        except Exception:
            try:
                import onnxruntime as ort
                import os
                import urllib.request

                model_path = "silero_vad.onnx"
                if not os.path.exists(model_path):
                    print("[VAD] Downloading Silero VAD model...")
                    url = "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx"
                    urllib.request.urlretrieve(url, model_path)

                self.model = ort.InferenceSession(model_path)
                self.onnx_mode = True
                print("[VAD] OK Silero VAD loaded (ONNX)")
            except Exception:
                print("[VAD] Using energy-based fallback VAD")
                self.model = None
                self.onnx_mode = False

    def is_speech(self, audio_chunk):
        """Return True when chunk is likely speech."""
        try:
            if self.model is None:
                energy = np.sqrt(np.mean(audio_chunk**2))
                return energy > 0.01

            if len(audio_chunk) != self.frame_size:
                if len(audio_chunk) < self.frame_size:
                    audio_chunk = np.pad(audio_chunk, (0, self.frame_size - len(audio_chunk)))
                else:
                    audio_chunk = audio_chunk[: self.frame_size]

            if self.onnx_mode:
                audio_tensor = audio_chunk.reshape(1, -1).astype(np.float32)
                sr_tensor = np.array([self.sample_rate], dtype=np.int64)
                speech_prob = self.model.run(None, {"input": audio_tensor, "sr": sr_tensor})[0][0][0]
            else:
                audio_tensor = torch.tensor(audio_chunk, dtype=torch.float32)
                with torch.no_grad():
                    speech_prob = self.model(audio_tensor, self.sample_rate).item()

            return speech_prob > self.trigger_level
        except Exception:
            return False


class STTEngine:
    """Speech to Text Engine."""

    def __init__(self, whisper_model="tiny"):
        print(f"[STT] Initializing with model: {whisper_model}")

        try:
            self.model = WhisperModel(
                whisper_model,
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
                num_workers=2,
            )
            print("[STT] OK Faster-Whisper loaded")
        except Exception as e:
            print(f"[STT] Failed: {e}")
            raise

        self.vad = SileroVAD()

        self.sample_rate = 16000
        self.frame_size = 512
        self.frame_duration = 32

        self.audio_buffer = []
        self.pre_speech_buffer = collections.deque()
        self.silence_counter = 0
        self.speech_counter = 0
        self.recording_started = False

        self.silence_timeout = 0.8
        self.max_duration = 10.0
        self.min_speech_duration = 0.5

        # Keep ~350ms pre-speech so the first word is not clipped.
        self.pre_roll_duration = 0.35
        self.pre_roll_frames = max(1, int((self.pre_roll_duration * self.sample_rate) / self.frame_size))

        self.ALLOWED_SINGLE_WORDS = {
            "jarvis",
            "stop",
            "quit",
            "exit",
            "offline",
            "calculator",
            "notepad",
            "paint",
            "camera",
            "youtube",
            "netflix",
            "google",
            "gmail",
            "chrome",
            "edge",
            "spotify",
            "word",
            "excel",
            "mute",
            "unmute",
            "home",
            "lock",
            "shutdown",
            "restart",
        }

        self.BLOCKED_PATTERNS = [
            "go, go, go",
            "go go go",
            "come on",
            "let's go",
            "goal",
            "score",
            "win",
            "hey hey",
            "hi hi",
            "yeah yeah",
            "yes yes",
            "no no",
            "ok ok",
            "uh huh",
            "ha ha",
            "haha",
            "lol",
            "test test",
            "one two three",
            "thank you",
            "i'm going to",
            "it's not a",
            "this is not a",
            "the quick brown fox",
            "hello world",
        ]

        print("[STT] OK Ready")

    def listen_for_speech(self):
        """Record one utterance using VAD start/end."""
        print("\n[VAD] Listening...")

        self.audio_buffer = []
        self.pre_speech_buffer = collections.deque(maxlen=self.pre_roll_frames)
        self.silence_counter = 0
        self.speech_counter = 0
        self.recording_started = False
        start_time = time.time()

        def audio_callback(indata, frames, time_info, status):
            del frames, time_info, status

            audio_chunk = indata[:, 0].astype(np.float32)
            self.pre_speech_buffer.append(audio_chunk.copy())
            is_speech = self.vad.is_speech(audio_chunk)
            started_this_chunk = False

            if is_speech:
                self.speech_counter += 1
                self.silence_counter = 0

                # Trigger quickly and prepend pre-roll context.
                if not self.recording_started and self.speech_counter >= 2:
                    self.recording_started = True
                    for pre_chunk in self.pre_speech_buffer:
                        self.audio_buffer.extend(pre_chunk)
                    started_this_chunk = True
                    print("\r[VAD] Speaking...", end="", flush=True)

                if self.recording_started and not started_this_chunk:
                    self.audio_buffer.extend(audio_chunk)
            else:
                self.speech_counter = 0
                if self.recording_started:
                    self.silence_counter += 1
                    self.audio_buffer.extend(audio_chunk)

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                callback=audio_callback,
                blocksize=self.frame_size,
            ):
                wait_start = time.time()
                while not self.recording_started and (time.time() - wait_start) < 5:
                    time.sleep(0.01)

                if not self.recording_started:
                    print("\r[VAD] No speech detected")
                    return None, 0

                silence_frames = int(self.silence_timeout * 1000 / self.frame_duration)
                while self.silence_counter < silence_frames and (time.time() - start_time) < self.max_duration:
                    time.sleep(0.01)

                duration = len(self.audio_buffer) / self.sample_rate
                if duration < self.min_speech_duration:
                    print(f"\r[VAD] Too short ({duration:.1f}s)")
                    return None, 0

                print(f"\r[VAD] Recorded {duration:.1f}s")
                audio_array = np.array(self.audio_buffer, dtype=np.float32)

                max_val = np.max(np.abs(audio_array))
                if max_val > 0:
                    audio_array = audio_array / max_val * 0.9

                return audio_array, duration
        except Exception as e:
            print(f"\r[VAD] Error: {e}")
            return None, 0

    def transcribe(self, audio):
        """Transcribe speech with Faster-Whisper."""
        if audio is None or len(audio) == 0:
            return None, 0.0

        try:
            segments, info = self.model.transcribe(
                audio,
                language="en",
                task="transcribe",
                beam_size=3,
                best_of=3,
                temperature=0.0,
                # Avoid running another VAD after external VAD capture.
                vad_filter=False,
                no_speech_threshold=0.6,
            )
            del info

            text_parts = [segment.text for segment in segments]
            if not text_parts:
                return None, 0.0

            text = " ".join(text_parts).strip()
            confidence = 0.85
            return text, confidence
        except Exception:
            return None, 0.0

    def is_false_positive(self, text):
        """Filter clear garbage/trigger phrases."""
        if not text:
            return True

        text_lower = text.lower().strip()

        for pattern in self.BLOCKED_PATTERNS:
            if pattern in text_lower:
                print("[FILTER] Blocked pattern")
                return True

        words = text_lower.split()
        if len(words) == 1 and words[0] not in self.ALLOWED_SINGLE_WORDS:
            print("[FILTER] Unauthorized single word")
            return True

        if "jarvis" not in text_lower and len(words) <= 2:
            print("[FILTER] No wake word")
            return True

        if len(text) < 3:
            print("[FILTER] Too short")
            return True

        return False

    def listen_blocking(self):
        """Capture + transcribe one utterance."""
        audio, duration = self.listen_for_speech()
        del duration

        if audio is None:
            return None, 0.0

        text, confidence = self.transcribe(audio)
        if not text:
            return None, 0.0

        if self.is_false_positive(text):
            return None, 0.0

        print(f"[STT] \"{text}\"")
        return text, confidence

    def cleanup(self):
        """Cleanup."""
        pass

