#!/usr/bin/env python3
"""
Enhanced Command Processing Module - ULTRA ROBUST WAKE WORD DETECTION
- Searches for wake word ANYWHERE in text (not just position 0)
- Aggressive fuzzy matching with multiple strategies
- Handles punctuation, word positions, and variations
- Cleans and validates extracted commands
"""
import os
import sys
import json
import webbrowser
import subprocess
import requests
import time
import re
import ctypes
from urllib.parse import parse_qs, unquote, urlparse
from datetime import datetime
from fuzzywuzzy import fuzz

class CommandProcessor:
    def __init__(self, groq_api_key, groq_model="llama-3.1-8b-instant"):
        """Initialize command processor with robust wake word detection"""
        self.groq_key = groq_api_key
        self.groq_model = groq_model
        self.query_max_tokens = 80
        self.query_temperature = 0.2
        self.manage_gesture_externally = False
        
        # Ultra-robust wake word settings
        self.wake_word_threshold = 72  # Slightly lower for common Whisper variants of "jarvis"
        self.secondary_threshold = 85  # For stricter second-pass validation
        self.min_wake_word_length = 3  # Lower threshold (was 4, now catches shorter variations)
        self.wake_word_aliases = {
            "jarves", "jervis", "harvis", "harviz", "arvis", "arves", "carvis", "carves"
        }
        
        # Intent patterns
        self.intent_patterns = {
            "open_app": {
                "keywords": ["open", "launch", "start", "run"],
                "confidence_boost": 0.9
            },
            "search": {
                "keywords": ["search", "google", "look up", "find", "what is"],
                "confidence_boost": 0.85
            },
            "type": {
                "keywords": ["type", "write", "enter", "input"],
                "confidence_boost": 0.8
            },
            "mute": {
                "keywords": ["mute", "unmute", "silence"],
                "confidence_boost": 0.85
            },
            "volume_up": {
                "keywords": ["increase volume", "volume up", "louder"],
                "confidence_boost": 0.9
            },
            "volume_down": {
                "keywords": ["decrease volume", "volume down", "quieter", "lower volume"],
                "confidence_boost": 0.9
            },
            "brightness_up": {
                "keywords": [
                    "increase brightness", "increased brightness", "brightness up",
                    "turn up brightness", "raise brightness", "brighter",
                ],
                "confidence_boost": 0.9
            },
            "brightness_down": {
                "keywords": [
                    "decrease brightness", "decreased brightness", "brightness down",
                    "turn down brightness", "reduce brightness", "lower brightness", "darker",
                ],
                "confidence_boost": 0.9
            },
            "home_screen": {
                "keywords": ["home screen", "go home", "show home", "minimize all"],
                "confidence_boost": 0.9
            },
            "shutdown": {
                "keywords": ["shutdown", "shut down", "turn off", "power off"],
                "confidence_boost": 0.95
            },
            "restart": {
                "keywords": ["restart", "reboot", "restart computer"],
                "confidence_boost": 0.95
            },
            "lock_screen": {
                "keywords": ["lock", "lock screen", "lock pc"],
                "confidence_boost": 0.9
            },
            "quit": {
                "keywords": ["quit", "exit", "stop", "offline", "close agent"],
                "confidence_boost": 0.95
            },
            "launch_gesture": {
                "keywords": ["gesture", "virtual mouse", "hand tracking", "gesture control", "start gesture"],
                "confidence_boost": 0.95
            },
            "screenshot": {
                "keywords": ["take screenshot", "screenshot", "screen shot", "capture screen"],
                "confidence_boost": 0.95
            }
        }
        
        # Websites
        self.websites = {
            "youtube": "https://youtube.com",
            "netflix": "https://netflix.com",
            "chatgpt": "https://chat.openai.com",
            "gmail": "https://mail.google.com",
            "google": "https://google.com",
            "facebook": "https://facebook.com",
            "twitter": "https://twitter.com",
            "linkedin": "https://linkedin.com",
            "reddit": "https://reddit.com",
        }
        
        # System apps
        self.system_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "camera": "microsoft.windows.camera:",
            "paint": "mspaint.exe",
            "word": self._find_office("WINWORD.EXE"),
            "microsoft word": self._find_office("WINWORD.EXE"),
            "powerpoint": self._find_office("POWERPNT.EXE"),
            "ppt": self._find_office("POWERPNT.EXE"),
            "excel": self._find_office("EXCEL.EXE"),
            "control panel": "control.exe",
            "settings": "ms-settings:",
            "this pc": "explorer.exe",
            "file explorer": "explorer.exe",
            "recycle bin": "shell:RecycleBinFolder",
            "bin": "shell:RecycleBinFolder",
            "trash": "shell:RecycleBinFolder",
        }
        
        # Try to import keyboard library
        self.keyboard = None
        try:
            from pynput import keyboard as kb
            self.keyboard = kb
        except Exception as e:
            print(f"[WARNING] pynput unavailable ({e}). Volume control will not work.")
        
        # Try to import brightness control
        self.brightness_lib = None
        try:
            import screen_brightness_control as sbc
            self.brightness_lib = sbc
        except ImportError:
            print("[INFO] screen-brightness-control not installed.")
    
    def _find_office(self, exe_name):
        """Find Office executable"""
        if sys.platform != "win32":
            return exe_name
        
        paths = [
            f"C:\\Program Files\\Microsoft Office\\root\\Office16\\{exe_name}",
            f"C:\\Program Files (x86)\\Microsoft Office\\root\\Office16\\{exe_name}",
            f"C:\\Program Files\\Microsoft Office\\Office16\\{exe_name}",
            f"C:\\Program Files (x86)\\Microsoft Office\\Office16\\{exe_name}",
        ]
        
        for path in paths:
            if os.path.exists(path):
                return f'"{path}"'
        
        return exe_name
    
    def _clean_word(self, word):
        """Remove punctuation from word"""
        return re.sub(r'[^\w]', '', word)
    
    def _find_wake_word_in_text(self, text, wake_word="jarvis"):
        """
        ULTRA ROBUST: Search for wake word ANYWHERE in text using multiple strategies
        
        Strategies:
        1. Check position 0 (most common)
        2. Search all words with fuzzy matching
        3. Check if wake word is embedded in longer words
        4. Handle punctuation variations
        
        Returns: (found, cleaned_command, best_score, position)
        """
        text_lower = " ".join(text.lower().split()).strip()
        
        if not text_lower:
            return False, None, 0, -1
        
        words = text_lower.split()
        best_match = None
        best_score = 0
        best_position = -1
        
        # Strategy 1 & 2: Check each word for fuzzy match
        for idx, word in enumerate(words):
            # Remove punctuation
            clean_word = self._clean_word(word)
            
            # Skip empty words or very short words
            if len(clean_word) < self.min_wake_word_length:
                continue
            
            # Fast alias path for common STT substitutions
            if clean_word in self.wake_word_aliases:
                score = 100
            else:
                # Fuzzy matching
                score = max(
                    fuzz.ratio(clean_word, wake_word),
                    fuzz.partial_ratio(clean_word, wake_word),
                )
            
            if score > best_score:
                best_score = score
                best_match = clean_word
                best_position = idx
        
        # Check if match meets threshold
        if best_score >= self.wake_word_threshold:
            # Build cleaned command by removing the wake word at that position
            remaining_words = [w for i, w in enumerate(words) if i != best_position]
            cleaned_command = " ".join(remaining_words).strip()
            
            print(f"[WAKE WORD] ✓ Found '{best_match}' at position {best_position} (score: {best_score}/100)")
            return True, cleaned_command, best_score, best_position
        
        # No match found
        if best_match:
            print(f"[WAKE WORD] ✗ Best match '{best_match}' has score {best_score}/100 (threshold: {self.wake_word_threshold})")
        else:
            print(f"[WAKE WORD] ✗ No words matched wake word '{wake_word}'")
        
        return False, None, best_score, -1
    
    def classify_intent(self, text):
        """Classify user intent"""
        text_lower = text.lower().strip()
        
        # Check websites first
        for site_name in self.websites:
            if site_name in text_lower:
                return ("open_website", 0.95, site_name)
        
        best_intent = None
        best_confidence = 0.0
        
        for intent, pattern_data in self.intent_patterns.items():
            keywords = pattern_data["keywords"]
            confidence_boost = pattern_data["confidence_boost"]
            
            for keyword in keywords:
                if keyword in text_lower:
                    confidence = confidence_boost
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_intent = intent
                    break
        
        if best_intent:
            param = self._extract_parameter(text_lower, best_intent)
            return (best_intent, best_confidence, param)
        
        return ("query", 0.5, text)
    
    def _extract_parameter(self, text, intent):
        """Extract parameter"""
        keywords = self.intent_patterns[intent]["keywords"]
        
        for keyword in keywords:
            if keyword in text:
                parts = text.split(keyword, 1)
                if len(parts) > 1:
                    param = parts[1].strip()
                    if intent in {"open_app", "open_website"}:
                        # Keep dots inside domains/URLs; remove only trailing sentence punctuation.
                        return re.sub(r"[.!?]+$", "", param).strip()
                    param = param.replace(".", "")
                    return param
        return ""
    
    def execute_command(self, intent, param):
        """Execute command"""
        if intent == "open_website":
            return self._open_website(param)
        elif intent == "open_app":
            return self._open_app(param)
        elif intent == "search":
            return self._search_web(param)
        elif intent == "type":
            return self._type_text(param)
        elif intent == "mute":
            return self._toggle_mute()
        elif intent == "volume_up":
            return self._volume_up()
        elif intent == "volume_down":
            return self._volume_down()
        elif intent == "brightness_up":
            return self._brightness_up()
        elif intent == "brightness_down":
            return self._brightness_down()
        elif intent == "home_screen":
            return self._go_home_screen()
        elif intent == "shutdown":
            return self._shutdown_pc()
        elif intent == "restart":
            return self._restart_pc()
        elif intent == "lock_screen":
            return self._lock_screen()
        elif intent == "quit":
            return self._quit_agent()
        elif intent == "launch_gesture":
            return self._launch_gesture()
        elif intent == "screenshot":
            return self._take_screenshot()
        elif intent == "query":
            return self._ask_llm(param)
        else:
            return "Unknown command."

    def _is_uri_target(self, target: str) -> bool:
        """Check if target is a Windows URI/protocol launch string."""
        return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target))

    def _normalize_website_url(self, target: str) -> str:
        """Normalize user input to a URL when possible."""
        target = target.strip()
        if not target:
            return ""
        target_lower = target.lower()
        if target_lower.startswith(("http://", "https://")):
            return target
        if target_lower.startswith("www."):
            return f"https://{target}"
        # Domain-like input: example.com, sub.example.org/path
        if re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)+([/?#].*)?$", target, flags=re.IGNORECASE):
            return f"https://{target}"
        return ""

    def _decode_search_redirect_url(self, href: str) -> str:
        """Decode search engine redirect links to their final destination URL."""
        if not href:
            return ""

        href = href.strip()
        if href.startswith("//"):
            href = f"https:{href}"

        parsed = urlparse(href)
        host = parsed.netloc.lower()
        query_params = parse_qs(parsed.query)

        # DuckDuckGo redirect format: /l/?uddg=<encoded_target>
        if "duckduckgo.com" in host and parsed.path.startswith("/l/"):
            uddg = query_params.get("uddg", [])
            if uddg:
                return unquote(uddg[0])

        # Google redirect format: /url?q=<target>
        if "google." in host and parsed.path == "/url":
            q_target = query_params.get("q", [])
            if q_target:
                return unquote(q_target[0])

        if href.startswith(("http://", "https://")):
            return href

        return ""

    def _resolve_first_search_result_url(self, target: str) -> str:
        """Resolve a plain-name website target to a direct URL via first search result."""
        query = f"{target} official website"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }

        try:
            response = requests.get(
                "https://duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
                timeout=6,
            )
            response.raise_for_status()
        except Exception:
            return ""

        # Typical result links use class="result__a"
        matches = re.findall(r'class="result__a"[^>]*href="([^"]+)"', response.text)
        for href in matches:
            resolved = self._decode_search_redirect_url(href)
            if resolved:
                return resolved

        return ""

    def _open_dynamic_website(self, target: str):
        """
        Open a website that is not preloaded.
        - If target is a URL/domain, open directly.
        - Otherwise, resolve the first search result and open that direct URL.
        """
        if not target or not target.strip():
            return "Please specify a website."

        target = target.strip()
        try:
            direct_url = self._normalize_website_url(target)
            if direct_url:
                webbrowser.open(direct_url)
                return f"Opening {target}."

            resolved_url = self._resolve_first_search_result_url(target)
            if resolved_url:
                webbrowser.open(resolved_url)
                return f"Opening {target} website."

            # Last fallback if search resolution fails due network/markup changes.
            webbrowser.open(f"https://www.google.com/search?q={target.replace(' ', '+')}+official+website")
            return f"I couldn't auto-resolve {target}. Showing search results."
        except Exception:
            return f"Failed to open {target}."
    
    def _open_website(self, site_name):
        """Open website"""
        site_name = site_name.lower().strip()
        if site_name in self.websites:
            webbrowser.open(self.websites[site_name])
            return f"Opening {site_name.capitalize()}."
        return self._open_dynamic_website(site_name)
    
    def _open_app(self, app_name):
        """Open system application"""
        if not app_name:
            return "Please specify an app."
        
        app_name_lower = app_name.lower().strip()

        if app_name_lower in {"whatsapp", "whats app"}:
            return self._open_whatsapp()
        
        # Try exact match first
        if app_name_lower in self.system_apps:
            app_cmd = self.system_apps[app_name_lower]
            try:
                if sys.platform == "win32" and self._is_uri_target(app_cmd):
                    # URI/protocol launch (e.g. microsoft.windows.camera:, ms-settings:)
                    os.startfile(app_cmd)
                else:
                    subprocess.Popen(app_cmd)
                return f"Opened {app_name}."
            except Exception:
                return f"Failed to open {app_name}."
        
        # Try conservative fuzzy matching for app names. Avoid partial matches so
        # unrelated names like "whatsapp" cannot match short aliases like "ppt".
        best_match, best_score = self._best_system_app_match(app_name_lower)
        if best_match and best_score >= 78:
            try:
                app_cmd = self.system_apps[best_match]
                if sys.platform == "win32" and self._is_uri_target(app_cmd):
                    os.startfile(app_cmd)
                else:
                    subprocess.Popen(app_cmd)
                return f"Opened {best_match}."
            except Exception:
                return f"Failed to open {best_match}."

        # Fallback: treat unknown app target as a website request.
        return self._open_dynamic_website(app_name)

    def _best_system_app_match(self, app_name: str):
        """Find a typo-tolerant system app match without substring traps."""
        best_match = None
        best_score = 0

        for candidate in self.system_apps:
            # Short aliases are useful only when the user says nearly the alias.
            if len(candidate) <= 3 and len(app_name) > 4:
                continue

            score = max(
                fuzz.ratio(app_name, candidate),
                fuzz.token_sort_ratio(app_name, candidate),
            )
            if score > best_score:
                best_match = candidate
                best_score = score

        return best_match, best_score

    def _open_whatsapp(self):
        """Open WhatsApp desktop when registered, otherwise open WhatsApp Web."""
        if sys.platform == "win32":
            for target in ("whatsapp://", "whatsapp:"):
                try:
                    os.startfile(target)
                    return "Opening WhatsApp."
                except Exception:
                    pass

        try:
            webbrowser.open("https://web.whatsapp.com")
            return "Opening WhatsApp Web."
        except Exception:
            return "Failed to open WhatsApp."
    
    def _search_web(self, query):
        """Search Google"""
        if not query:
            return "Please specify a search query."
        
        webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
        return f"Searching for: {query}"
    
    def _type_text(self, text):
        """Type text"""
        if not text:
            return "No text to type."
        
        try:
            from pynput.keyboard import Controller
            Controller().type(text)
            return "Text typed."
        except ImportError:
            return "Install pynput: pip install pynput"
        except Exception:
            return "Failed to type."
    
    def _toggle_mute(self):
        """Toggle mute"""
        try:
            if self.keyboard and sys.platform == "win32":
                self.keyboard.Controller().press(self.keyboard.Key.media_volume_mute)
                self.keyboard.Controller().release(self.keyboard.Key.media_volume_mute)
                return "Toggled mute."
            if sys.platform == "win32":
                # Fallback: native Windows media key event
                self._send_windows_media_key(0xAD)  # VK_VOLUME_MUTE
                return "Toggled mute."
        except Exception:
            pass
        return "Mute control not available."
    
    def _volume_up(self):
        """Increase volume"""
        try:
            if self.keyboard and sys.platform == "win32":
                for _ in range(3):
                    self.keyboard.Controller().press(self.keyboard.Key.media_volume_up)
                    self.keyboard.Controller().release(self.keyboard.Key.media_volume_up)
                    time.sleep(0.1)
                return "Volume increased."
            if sys.platform == "win32":
                for _ in range(3):
                    self._send_windows_media_key(0xAF)  # VK_VOLUME_UP
                    time.sleep(0.1)
                return "Volume increased."
            return "Volume control not supported on this platform."
        except Exception:
            return "Volume control error."
    
    def _volume_down(self):
        """Decrease volume"""
        try:
            if self.keyboard and sys.platform == "win32":
                for _ in range(3):
                    self.keyboard.Controller().press(self.keyboard.Key.media_volume_down)
                    self.keyboard.Controller().release(self.keyboard.Key.media_volume_down)
                    time.sleep(0.1)
                return "Volume decreased."
            if sys.platform == "win32":
                for _ in range(3):
                    self._send_windows_media_key(0xAE)  # VK_VOLUME_DOWN
                    time.sleep(0.1)
                return "Volume decreased."
            return "Volume control not supported on this platform."
        except Exception:
            return "Volume control error."

    def _send_windows_media_key(self, vk_code: int):
        """Send a Windows media key press/release event."""
        keyeventf_keyup = 0x0002
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, keyeventf_keyup, 0)
    
    def _brightness_up(self):
        """Increase brightness"""
        return self._adjust_brightness(10, "increased")
    
    def _brightness_down(self):
        """Decrease brightness"""
        return self._adjust_brightness(-10, "decreased")

    def _adjust_brightness(self, delta: int, action_word: str):
        """Adjust brightness and verify that the display accepted the change."""
        current = self._get_brightness()
        if current is None:
            return "Brightness control not available for this display."

        target = max(10, min(current + delta, 100))
        if target == current:
            if delta > 0:
                return "Brightness is already at maximum."
            return "Brightness is already at minimum."

        if not self._set_brightness(target):
            return "Brightness control not available for this display."

        time.sleep(0.4)
        verified = self._get_brightness()
        if verified is None:
            return "Brightness change sent, but I could not verify it."

        if abs(verified - target) <= 2 or (delta > 0 and verified > current) or (delta < 0 and verified < current):
            return f"Brightness {action_word} to {verified}%."

        return "Brightness command was sent, but the display did not change."

    def _get_brightness(self):
        """Read brightness using Python library first, then Windows WMI."""
        if self.brightness_lib:
            try:
                values = self.brightness_lib.get_brightness()
                if values:
                    return int(values[0])
            except Exception:
                pass

        return self._get_windows_wmi_brightness()

    def _set_brightness(self, value: int) -> bool:
        """Set brightness using all available backends."""
        success = False

        if self.brightness_lib:
            try:
                self.brightness_lib.set_brightness(value)
                success = True
            except Exception:
                pass

        if sys.platform == "win32":
            success = self._set_windows_wmi_brightness(value) or success

        return success

    def _get_windows_wmi_brightness(self):
        """Read Windows internal-display brightness via WMI."""
        if sys.platform != "win32":
            return None

        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | "
                    "Select-Object -First 1 -ExpandProperty CurrentBrightness)",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            output = result.stdout.strip()
            if not output:
                return None
            return int(output.splitlines()[0].strip())
        except Exception:
            return None

    def _set_windows_wmi_brightness(self, value: int) -> bool:
        """Set Windows internal-display brightness via WMI."""
        if sys.platform != "win32":
            return False

        value = max(0, min(int(value), 100))
        ps_script = (
            "$methods = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods; "
            f"foreach ($method in $methods) {{ Invoke-CimMethod -InputObject $method -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={value}}} | Out-Null }}"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _go_home_screen(self):
        """Minimize all windows"""
        try:
            if sys.platform == "win32":
                subprocess.run(["powershell", "-Command", 
                    "Add-Type -AssemblyName System.Windows.Forms; " +
                    "[System.Windows.Forms.SendKeys]::SendWait('%m')"],
                    check=False)
                return "Minimized all apps."
            else:
                return "Not supported on this platform."
        except Exception:
            return "Failed to minimize apps."
    
    def _shutdown_pc(self):
        """Shutdown"""
        try:
            if sys.platform == "win32":
                subprocess.run(["shutdown", "/s", "/t", "10"], check=False)
                return "Shutting down in 10 seconds."
            else:
                subprocess.run(["shutdown", "-h", "+0"], check=False)
                return "Shutting down."
        except Exception:
            return "Shutdown failed."
    
    def _restart_pc(self):
        """Restart"""
        try:
            if sys.platform == "win32":
                subprocess.run(["shutdown", "/r", "/t", "10"], check=False)
                return "Restarting in 10 seconds."
            else:
                subprocess.run(["shutdown", "-r", "+0"], check=False)
                return "Restarting."
        except Exception:
            return "Restart failed."
    
    def _lock_screen(self):
        """Lock screen"""
        try:
            if sys.platform == "win32":
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
                return "Screen locked."
            else:
                return "Not supported on this platform."
        except Exception:
            return "Failed to lock screen."
    
    def _launch_gesture(self):
        """Launch gesture agent"""
        if self.manage_gesture_externally:
            return "LAUNCH_GESTURE"
        try:
            gesture_script = os.path.join(os.path.dirname(__file__), "gesture.py")
            if not os.path.exists(gesture_script):
                gesture_script = "gesture.py"
            
            if os.path.exists(gesture_script):
                subprocess.Popen([sys.executable, gesture_script])
                return "Gesture agent launched."
            else:
                return "gesture.py not found."
        except Exception as e:
            return f"Failed to launch gesture agent."

    def _take_screenshot(self):
        """Capture full-screen screenshot and save PNG."""
        if sys.platform != "win32":
            return "Screenshot command is currently supported on Windows only."

        try:
            home_dir = os.path.expanduser("~")
            onedrive_dir = os.environ.get("OneDrive", "").strip()

            candidate_dirs = []
            if onedrive_dir:
                candidate_dirs.append(os.path.join(onedrive_dir, "Pictures", "Screenshots"))
            candidate_dirs.append(os.path.join(home_dir, "Pictures", "Screenshots"))

            screenshots_dir = None
            for candidate in candidate_dirs:
                parent = os.path.dirname(candidate)
                if os.path.exists(parent):
                    screenshots_dir = candidate
                    break

            if screenshots_dir is None:
                screenshots_dir = candidate_dirs[0]

            os.makedirs(screenshots_dir, exist_ok=True)
            filename = f"Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            output_path = os.path.join(screenshots_dir, filename)

            ps_output_path = output_path.replace("'", "''")
            ps_script = (
                "$ErrorActionPreference = 'Stop'; "
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; "
                "public static class NativeMethods { "
                "[DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware(); "
                "[DllImport(\"user32.dll\")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value); }'; "
                "if (-not [NativeMethods]::SetProcessDpiAwarenessContext([IntPtr](-4))) { "
                "  [void][NativeMethods]::SetProcessDPIAware(); "
                "} "
                "$screens = [System.Windows.Forms.Screen]::AllScreens; "
                "$left = ($screens | ForEach-Object { $_.Bounds.Left } | Measure-Object -Minimum).Minimum; "
                "$top = ($screens | ForEach-Object { $_.Bounds.Top } | Measure-Object -Minimum).Minimum; "
                "$right = ($screens | ForEach-Object { $_.Bounds.Right } | Measure-Object -Maximum).Maximum; "
                "$bottom = ($screens | ForEach-Object { $_.Bounds.Bottom } | Measure-Object -Maximum).Maximum; "
                "$width = [int]($right - $left); "
                "$height = [int]($bottom - $top); "
                "$bmp = New-Object System.Drawing.Bitmap $width, $height; "
                "$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
                "$gfx.CopyFromScreen($left, $top, 0, 0, $bmp.Size, [System.Drawing.CopyPixelOperation]::SourceCopy); "
                f"$bmp.Save('{ps_output_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
                "$gfx.Dispose(); "
                "$bmp.Dispose();"
            )

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and os.path.exists(output_path):
                return "Screenshot taken."
            return "Failed to take screenshot."
        except Exception:
            return "Failed to take screenshot."
    
    def _quit_agent(self):
        """Quit agent"""
        return "QUIT_AGENT"
    
    def _ask_llm(self, prompt):
        """Query Groq LLM"""
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.groq_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a voice assistant. Give concise, direct answers for spoken queries. "
                                "Keep replies under 3 short sentences unless the user explicitly asks for details."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self.query_temperature,
                    "max_tokens": self.query_max_tokens
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            else:
                return "API error."
        except Exception:
            return "Query failed."
    
    def process(self, user_input, wake_word="jarvis"):
        """
        ULTRA ROBUST main entry point
        - Searches for wake word ANYWHERE in text
        - Handles punctuation, position variations, and fuzzy matching
        """
        user_input = " ".join(user_input.lower().split()).strip()
        
        # ULTRA ROBUST: Find wake word anywhere in text
        found, cleaned_text, score, position = self._find_wake_word_in_text(user_input, wake_word)
        
        if not found:
            print(f"[REJECT] Wake word not detected. Best match score: {score}/100 (threshold: {self.wake_word_threshold})")
            return None  # Reject command
        
        # Use cleaned command (wake word removed)
        user_input = cleaned_text
        
        if not user_input.strip():
            print(f"[WARN] Empty command after wake word removal")
            return "I didn't catch the command. Please repeat."
        
        intent, confidence, param = self.classify_intent(user_input)
        
        print(f"[INTENT] {intent.upper()} (confidence: {confidence:.2f}) | param: {param}")
        
        if intent in ["volume_up", "volume_down", "brightness_up", "brightness_down", 
                      "home_screen", "shutdown", "restart", "lock_screen", "launch_gesture", "quit"]:
            min_confidence = 0.70
        else:
            min_confidence = 0.3
        
        if confidence < min_confidence and intent != "query":
            response = self._ask_llm(user_input)
        else:
            response = self.execute_command(intent, param)
        
        return response
