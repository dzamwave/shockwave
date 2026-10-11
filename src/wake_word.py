import os
import sys
import json
import re
import time
import queue
import threading
import sounddevice as sd
import numpy as np

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import vosk
except ImportError:
    vosk = None

import config

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidate = os.path.join(root_path, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

def ensure_vosk_model(model_dir=None):
    """Ensures Vosk model files exist locally. If missing, downloads from mirror list."""
    target_dir = model_dir or getattr(config, "VOSK_MODEL_PATH", None) or os.path.join(config.MODELS_DIR, "vosk-model-small-ru")
    if os.path.exists(target_dir):
        files = [f for f in os.listdir(target_dir) if f != ".gitkeep"]
        if files:
            return target_dir

    import urllib.request
    import zipfile

    mirrors = []
    custom_url = getattr(config, "VOSK_MODEL_URL", None)
    if custom_url:
        mirrors.append(custom_url)
    default_mirrors = [
        "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
        "https://huggingface.co/alphacep/vosk-model-small-ru/resolve/main/vosk-model-small-ru-0.22.zip"
    ]
    for m in default_mirrors:
        if m not in mirrors:
            mirrors.append(m)

    os.makedirs(config.MODELS_DIR, exist_ok=True)
    temp_zip = os.path.join(config.MODELS_DIR, "vosk_temp.zip")

    downloaded = False
    for url in mirrors:
        try:
            print(f"[WakeWord] Downloading Vosk model from: {url} ...")
            urllib.request.urlretrieve(url, temp_zip)
            downloaded = True
            print("[WakeWord] Download complete. Extracting...")
            break
        except Exception as err:
            print(f"[WakeWord] Mirror failed ({url}): {err}. Trying next mirror...")

    if not downloaded:
        print("[WakeWord] Error: Could not download Vosk model from any mirror.")
        return None

    try:
        with zipfile.ZipFile(temp_zip, 'r') as z:
            z.extractall(config.MODELS_DIR)
        if os.path.exists(temp_zip):
            os.remove(temp_zip)

        extracted = os.path.join(config.MODELS_DIR, "vosk-model-small-ru-0.22")
        if os.path.exists(extracted) and not os.path.exists(target_dir):
            os.rename(extracted, target_dir)
        return target_dir
    except Exception as e:
        print(f"[WakeWord] Extraction error: {e}")
        return None

class WakeWordDetector:
    def __init__(self, on_wake_callback=None, model_path=None, keyword=None):
        self.on_wake_callback = on_wake_callback
        self.keyword = (keyword or getattr(config, "WAKE_WORD", "мегатрон")).lower().strip()
        
        default_model = getattr(config, "VOSK_MODEL_PATH", None) or os.path.join(config.MODELS_DIR, "vosk-model-small-ru")
        self.model_path = model_path or default_model
        
        self.model = None
        self.recognizer = None
        self.stream = None
        
        self._is_enabled = False
        self._is_listening_mic = False
        self._last_trigger_time = 0.0
        self._lock = threading.Lock()
        self._audio_q = queue.Queue()
        
        # Deferred loading: Vosk model is loaded only when enable() / start_mic() is invoked.

    def _init_model(self):
        if self.model and self.recognizer:
            return
        if not vosk:
            print("[WakeWord] Error: Vosk library is not installed.")
            return

        candidate_path = ensure_vosk_model(self.model_path) or self.model_path
        if not os.path.exists(candidate_path):
            candidate_path = get_resource_path(candidate_path)
            
        if not os.path.exists(candidate_path):
            print(f"[WakeWord] Vosk model not found at {candidate_path}.")
            return

        try:
            print(f"[WakeWord] Loading full Vosk Russian model from: {candidate_path} ...")
            # Suppress excessive Vosk log spam
            vosk.SetLogLevel(-1)
            self.model = vosk.Model(candidate_path)
            # Use full language model vocabulary so Vosk accurately distinguishes all words
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            print(f"[WakeWord] Detector ready with full vocabulary for keyword: '{self.keyword}'")
        except Exception as e:
            print(f"[WakeWord] Model init error: {e}")

    def set_keyword(self, new_keyword):
        """Dynamically updates the wake keyword."""
        with self._lock:
            self.keyword = new_keyword.strip().lower()
            if self.recognizer:
                self.recognizer.Reset()
            print(f"[WakeWord] Detector reconfigured for keyword: '{self.keyword}'")

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice.RawInputStream for each audio buffer."""
        if status:
            pass
        if self._is_listening_mic and self._is_enabled:
            self._process_pcm(bytes(indata))

    def feed_audio(self, pcm_data):
        """Allows feeding audio chunks directly from an external stream (e.g. AudioEngine)."""
        if not self._is_enabled or not self.recognizer:
            return
            
        if isinstance(pcm_data, np.ndarray):
            # Convert float32 [-1.0, 1.0] to int16 bytes
            pcm_bytes = (pcm_data * 32767).astype(np.int16).tobytes()
        elif isinstance(pcm_data, (bytes, bytearray)):
            pcm_bytes = bytes(pcm_data)
        else:
            return
            
        self._process_pcm(pcm_bytes)

    def _process_pcm(self, pcm_bytes):
        with self._lock:
            if not self.recognizer:
                return

            now = time.time()
            # Anti-rebound cooldown: ignore hits within 2.0s of last trigger
            if now - self._last_trigger_time < 2.0:
                return

            detected = False
            kw_clean = self.keyword.strip().lower()
            pattern = r'(?:\b|^)' + re.escape(kw_clean) + r'(?:\b|$)'

            if self.recognizer.AcceptWaveform(pcm_bytes):
                res = json.loads(self.recognizer.Result())
                text = res.get("text", "").lower().strip()
                if text:
                    words = text.split()
                    if kw_clean in words or re.search(pattern, text):
                        detected = True
            else:
                pres = json.loads(self.recognizer.PartialResult())
                ptext = pres.get("partial", "").lower().strip()
                if ptext:
                    p_words = ptext.split()
                    # Only match if the exact keyword appears as a standalone word
                    if kw_clean in p_words:
                        detected = True

            if detected:
                self._last_trigger_time = now
                self.recognizer.Reset()
                print(f"\n[WakeWord] Exact trigger word detected: '{self.keyword}'!")
                if self.on_wake_callback:
                    threading.Thread(target=self.on_wake_callback, daemon=True).start()

    def start_mic(self):
        """Starts background microphone stream for wake word detection."""
        with self._lock:
            if not self.model or not self.recognizer:
                self._init_model()
                if not self.model:
                    return

            if self.stream is not None:
                return

            try:
                self._is_listening_mic = True
                self.stream = sd.RawInputStream(
                    samplerate=16000,
                    blocksize=4000,
                    dtype='int16',
                    channels=1,
                    callback=self._audio_callback
                )
                self.stream.start()
            except Exception as e:
                print(f"[WakeWord] Failed to open microphone stream: {e}")
                self.stream = None
                self._is_listening_mic = False

    def pause_mic(self):
        """Temporarily halts internal mic capture (e.g. when main recording stream is active)."""
        with self._lock:
            self._is_listening_mic = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

    def resume_mic(self):
        """Resumes internal mic capture if wake word is enabled."""
        if self._is_enabled:
            self.start_mic()

    def enable(self):
        """Enables wake word detection and starts listening."""
        self._is_enabled = True
        threading.Thread(target=self.start_mic, daemon=True).start()

    def unload_model(self):
        """Unloads Vosk model and recognizer from memory and releases OS pages."""
        with self._lock:
            if self.model is None and self.recognizer is None:
                return
            print("[WakeWord] Unloading Vosk model from memory...")
            self.recognizer = None
            self.model = None
            import gc
            gc.collect()
            try:
                import ctypes
                h_proc = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.psapi.EmptyWorkingSet(h_proc)
            except Exception:
                pass
            print("[WakeWord] Vosk model unloaded successfully. Memory freed.")

    def disable(self):
        """Disables wake word detection, closes microphone stream, and unloads model."""
        self._is_enabled = False
        self.pause_mic()
        self.unload_model()

    def is_enabled(self):
        return self._is_enabled
