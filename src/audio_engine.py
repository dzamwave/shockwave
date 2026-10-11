import numpy as np
import sounddevice as sd
import soundfile as sf
import time
import os
import threading

import config

import importlib.metadata
_original_version = importlib.metadata.version
def _safe_version(pkg_name):
    if "onnx" in pkg_name or "asr" in pkg_name:
        return "0.12.0"
    try:
        return _original_version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"
importlib.metadata.version = _safe_version

class AudioEngine:
    def __init__(self):
        self.stream = None
        self.audio_data = []
        self.sample_rate = 16000
        self.is_recording = False
        self.on_audio_chunk = None
        
        self.engine_type = (os.getenv("STT_ENGINE") or config.STT_ENGINE).lower()
        self.model = None
        self._model_lock = threading.Lock()
        self._is_loading_model = False
        self._last_used_time = 0.0
        self._stop_watchdog = False
        
        idle_timeout = getattr(config, "MODEL_IDLE_TIMEOUT", 300)
        timeout_desc = f"{idle_timeout}s" if idle_timeout > 0 else "disabled"
        print(f"[AudioEngine] STT Engine ({self.engine_type}) initialized with lazy loading (idle timeout: {timeout_desc}).")
        
        # Background watchdog to unload model from memory after idle timeout
        self._watchdog_thread = threading.Thread(target=self._idle_watchdog, daemon=True)
        self._watchdog_thread.start()

    def get_or_load_model(self):
        """Loads STT model into memory on demand (lazy loading)."""
        with self._model_lock:
            if self.model is not None:
                return self.model
                
            self.engine_type = (os.getenv("STT_ENGINE") or config.STT_ENGINE).lower()
            print(f"\n[AudioEngine] Loading STT model ({self.engine_type}) into memory...")
            start_t = time.time()
            
            if self.engine_type == "gigaam":
                try:
                    import onnx_asr
                    model_name = config.GIGAAM_MODEL
                    quant = config.GIGAAM_QUANTIZATION if config.GIGAAM_QUANTIZATION else None
                    gigaam_path = config.GIGAAM_MODEL_PATH if config.GIGAAM_MODEL_PATH else config.GIGAAM_DIR
                    
                    sess_options = None
                    if getattr(config, "ONNX_OPTIMIZE_MEMORY", True):
                        try:
                            import onnxruntime as ort
                            sess_options = ort.SessionOptions()
                            sess_options.enable_cpu_mem_arena = False
                            sess_options.enable_mem_pattern = False
                            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                            sess_options.intra_op_num_threads = min(4, os.cpu_count() or 4)
                            sess_options.inter_op_num_threads = 1
                            print("[AudioEngine] ONNX memory optimizations applied (arena=False, pattern=False).")
                        except Exception as e:
                            print(f"[AudioEngine] Could not configure ONNX session options: {e}")
                            sess_options = None
                    
                    print(f"[AudioEngine] Loading GigaAM model: {model_name} (quantization={quant}) ...")
                    if os.path.exists(gigaam_path) and os.listdir(gigaam_path):
                        print(f"[AudioEngine] Loading from local path: {gigaam_path}")
                        self.model = onnx_asr.load_model(model_name, path=gigaam_path, quantization=quant, sess_options=sess_options)
                    else:
                        self.model = onnx_asr.load_model(model_name, quantization=quant, sess_options=sess_options)
                    print(f"[AudioEngine] GigaAM model loaded successfully in {time.time() - start_t:.2f}s.")
                except Exception as e:
                    print(f"[AudioEngine] Error loading GigaAM: {e}")
                    self.model = None
            else:
                try:
                    from faster_whisper import WhisperModel
                    whisper_path = config.WHISPER_MODEL_PATH if config.WHISPER_MODEL_PATH else config.WHISPER_DIR
                    cpu_threads = min(4, os.cpu_count() or 4)
                    
                    if os.path.exists(whisper_path) and os.path.exists(os.path.join(whisper_path, "model.bin")):
                        print(f"[AudioEngine] Loading Whisper model from local path: {whisper_path} ...")
                        self.model = WhisperModel(whisper_path, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
                    else:
                        model_name = config.WHISPER_MODEL
                        print(f"[AudioEngine] Loading Whisper model by name: {model_name} ...")
                        self.model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=whisper_path, cpu_threads=cpu_threads)
                    print(f"[AudioEngine] Whisper model loaded successfully in {time.time() - start_t:.2f}s.")
                except Exception as e:
                    print(f"[AudioEngine] Error loading Whisper: {e}")
                    self.model = None
                    
            self._last_used_time = time.time()
            return self.model

    def preload_model_async(self):
        """Starts loading STT model in background while recording audio to minimize transcription latency."""
        if self.model is None and not self._is_loading_model:
            def _loader():
                self._is_loading_model = True
                try:
                    self.get_or_load_model()
                finally:
                    self._is_loading_model = False
            threading.Thread(target=_loader, daemon=True).start()

    def unload_model(self):
        """Unloads STT model and frees memory back to the operating system."""
        with self._model_lock:
            if self.model is None:
                return
            print(f"\n[AudioEngine] Idle timeout reached. Unloading STT model ({self.engine_type}) from memory...")
            self.model = None
            import gc
            gc.collect()
            try:
                import ctypes
                h_proc = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.psapi.EmptyWorkingSet(h_proc)
            except Exception:
                pass
            print("[AudioEngine] STT model unloaded successfully. Memory freed.")

    def _idle_watchdog(self):
        """Monitors model inactivity and unloads when idle timeout is exceeded."""
        while not self._stop_watchdog:
            time.sleep(5)
            timeout = getattr(config, "MODEL_IDLE_TIMEOUT", 300)
            if timeout <= 0:
                continue
            if self.is_recording:
                continue
            if self.model is not None and not self._is_loading_model:
                if (time.time() - self._last_used_time) >= timeout:
                    self.unload_model()

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block."""
        if status:
            pass
        if self.is_recording:
            self.audio_data.append(indata.copy())
            if self.on_audio_chunk:
                self.on_audio_chunk(indata)

    def start_recording(self):
        # Asynchronously load/warm up STT model during speech to avoid post-recording latency
        self.preload_model_async()
        self.audio_data = []
        self.is_recording = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback
        )
        self.stream.start()

    def stop_recording(self, trim_seconds=0.0):
        if self.stream:
            self.is_recording = False
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        if trim_seconds > 0.0 and self.audio_data:
            samples_to_trim = int(trim_seconds * self.sample_rate)
            audio_np = np.concatenate(self.audio_data, axis=0).flatten()
            if len(audio_np) > samples_to_trim:
                trimmed_np = audio_np[:-samples_to_trim]
                self.audio_data = [trimmed_np.reshape(-1, 1)]
                print(f"[AudioEngine] Trimmed last {trim_seconds}s from recording.")

    def cancel_recording(self):
        """Immediately stops the stream and flushes all audio buffers without saving."""
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.audio_data = []
        self._last_used_time = time.time()
        print("Recording cancelled and audio buffer discarded.")

    def transcribe(self) -> str:
        model = self.get_or_load_model()
        if not model:
            print("Error: No STT model loaded.")
            return ""
            
        if not self.audio_data:
            print("Error: No audio data recorded.")
            return ""
            
        # Concatenate audio chunks and flatten to 1D array
        audio_np = np.concatenate(self.audio_data, axis=0).flatten()
        duration = len(audio_np) / self.sample_rate
        
        if duration < 0.5:
            print("Error: Audio too short!")
            return ""
        
        try:
            if self.engine_type == "gigaam":
                # onnx_asr processing
                text = model.recognize(audio_np)
                if not isinstance(text, str):
                    text = str(text)
                
                print(f"GigaAM output: {text}")
                self._last_used_time = time.time()
                return text.strip()
                
            else:
                # faster-whisper processing
                whisper_lang = os.getenv("WHISPER_LANGUAGE", config.WHISPER_LANGUAGE)
                if whisper_lang:
                    whisper_lang = whisper_lang.strip().lower()
                    if whisper_lang in ["auto", "none", ""]:
                        whisper_lang = None
                else:
                    whisper_lang = None
                    
                segments, info = model.transcribe(audio_np, language=whisper_lang)
                text = " ".join([segment.text for segment in segments])
                print(f"Whisper output ({whisper_lang if whisper_lang else 'auto'}): {text}")
                self._last_used_time = time.time()
                return text.strip()
                
        except Exception as e:
            print(f"Transcription exception: {e}")
            return ""

    def cleanup(self):
        """Stops background watchdog, halts recording, and unloads model."""
        self._stop_watchdog = True
        self.stop_recording()
        self.unload_model()
