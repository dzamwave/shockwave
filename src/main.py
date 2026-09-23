import threading
import queue
import time
import sys
import os
from datetime import datetime

import config

from ui import WinVoiceUI, get_resource_path, play_ready_sound
from audio_engine import AudioEngine
from llm_normalizer import LLMNormalizer
from typer import Typer
from hotkey_manager import SystemHotkeyManager
from single_instance import check_single_instance, release_single_instance
from tray_manager import SystemTrayManager, hide_console, show_console
from wake_word import WakeWordDetector
from glossary import GlossaryManager

class WinVoiceApp:
    def __init__(self, is_silent=False):
        # 1. Single-Instance Protection: Prevent multiple instances running simultaneously
        if not check_single_instance():
            print("\n[Shockwave] Программа уже запущена! / Shockwave is already running!")
            time.sleep(1.5)
            sys.exit(0)
            
        self.is_silent = is_silent
        self.q = queue.Queue()
        self.audio = AudioEngine()
        self.llm = LLMNormalizer()
        self.typer = Typer()
        self.glossary = GlossaryManager(getattr(config, "GLOSSARY_PATH", None))
        
        self.is_recording = False
        self.is_processing = False
        self._recording_id = 0
        self.lock = threading.Lock()
        
        # 2. Wake Word Detector (Vosk)
        self.wake_detector = WakeWordDetector(on_wake_callback=self.on_wake_trigger)
        self.audio.on_audio_chunk = self.wake_detector.feed_audio
        
        # Initialize UI with click-to-trigger handler, cancel handler and wake word toggle
        self.ui = WinVoiceUI(
            self.q,
            position=config.UI_POSITION,
            on_trigger=self.toggle_recording,
            on_cancel=self.cancel_recording,
            on_toggle_wake=self.on_toggle_wake
        )
        
        # Activate wake word listener if enabled in settings
        if self.ui.wake_enabled:
            self.wake_detector.enable()
        
        # 3. System Tray Manager: Place Shockwave icon next to clock with toggle & exit menu
        icon_path = get_resource_path(os.path.join("icons", "icon.ico"))
        self.tray = SystemTrayManager(
            icon_path=icon_path,
            tooltip=f"Shockwave v{getattr(config, 'APP_VERSION', '1.0.0')}",
            on_quit=self.quit_app,
            on_show_widget=self.show_widget_topmost
        )
        self.tray.start()
        
        # 4. Register permanent system-level hotkey via Win32 RegisterHotKey
        self.hotkey_mgr = SystemHotkeyManager(config.HOTKEY, self.toggle_recording)
        yellow_radar = "\033[38;2;255;215;0m\033[1mRadar\033[0m"
        wake_keyword = getattr(config, "WAKE_WORD", "мегатрон")
        print(f"Shockwave started. Press {config.HOTKEY.upper()}, click {yellow_radar} or say '{wake_keyword.capitalize()}' to record.")
        
        # Hide console window to system tray smoothly
        hide_console()

    def show_widget_topmost(self):
        """Signals UI queue to display floating widget and bring it topmost above all windows."""
        self.q.put({"cmd": "show_topmost"})

    def on_toggle_wake(self, is_enabled):
        if is_enabled:
            print("[Shockwave] Wake word detection enabled.")
            self.wake_detector.enable()
        else:
            print("[Shockwave] Wake word detection disabled.")
            self.wake_detector.disable()

    def on_wake_trigger(self):
        """Called automatically when the wake word ('Мегатрон') is detected."""
        with self.lock:
            if self.is_processing:
                return
                
            if not self.is_recording:
                # First 'Мегатрон': start voice recording
                self.is_recording = True
                self.wake_detector.pause_mic()
                if self.ui.alert_enabled:
                    play_ready_sound()
                threading.Thread(target=self.start_recording_thread, daemon=True).start()
            else:
                # Second 'Мегатрон': stop recording with wake word trimming
                self.is_recording = False
                self.is_processing = True
                threading.Thread(target=lambda: self.process_audio_thread(is_wake_word=True), daemon=True).start()

    def cancel_recording(self):
        """Discards active recording immediately and resets UI state."""
        with self.lock:
            if not self.is_recording:
                return
            print("Cancelling recording upon user request...")
            self.is_recording = False
            self.is_processing = False
            self.audio.cancel_recording()
            self.wake_detector.resume_mic()
            self.q.put({"cmd": "show", "text": "what is your command?"})

    def toggle_recording(self):
        with self.lock:
            if self.is_processing:
                return
                
            if not self.is_recording:
                self.is_recording = True
                self.wake_detector.pause_mic()
                threading.Thread(target=self.start_recording_thread, daemon=True).start()
            else:
                self.is_recording = False
                self.is_processing = True
                threading.Thread(target=lambda: self.process_audio_thread(is_wake_word=False), daemon=True).start()

    def _recording_watchdog(self, rec_id):
        warn_seconds = getattr(config, "WARN_RECORD_SECONDS", 150)
        max_seconds = getattr(config, "MAX_RECORD_SECONDS", 180)
        warned = False
        start_time = time.time()
        
        while True:
            time.sleep(0.25)
            with self.lock:
                if not self.is_recording or self._recording_id != rec_id:
                    break
                
                elapsed = time.time() - start_time
                if not warned and elapsed >= warn_seconds:
                    warned = True
                    self.q.put({"cmd": "radar_warning"})
                    
                if elapsed >= max_seconds:
                    yellow_auto = "\033[38;2;255;180;50m\033[1m[Auto-Stop]\033[0m"
                    print(f"\n{yellow_auto} Reached {max_seconds}s limit. Stopping recording automatically...")
                    self.is_recording = False
                    self.is_processing = True
                    threading.Thread(target=lambda: self.process_audio_thread(is_wake_word=False), daemon=True).start()
                    break

    def start_recording_thread(self):
        with self.lock:
            self._recording_id += 1
            rec_id = self._recording_id
            
        start_time = datetime.now().strftime("%H:%M:%S")
        purple_start = "\033[38;2;180;95;235m\033[1mStarted recording\033[0m"
        print(f"\n{purple_start} {start_time}. ", end="", flush=True)
        self.q.put({"cmd": "show", "text": "record"})
        self.audio.start_recording()
        threading.Thread(target=lambda: self._recording_watchdog(rec_id), daemon=True).start()

    def process_audio_thread(self, is_wake_word=False):
        print("Stopping recording.")
        self.q.put({"cmd": "show", "text": "processing"})
        
        # Trim last ~1.1 seconds only if recording was stopped by saying the wake word
        trim_duration = 1.1 if is_wake_word else 0.0
        self.audio.stop_recording(trim_seconds=trim_duration)
        raw_text = self.audio.transcribe()
        
        if raw_text:
            # Apply user glossary substitutions
            processed_text = self.glossary.apply(raw_text)
            if processed_text != raw_text:
                cyan_glossary = "\033[38;2;100;200;255m\033[1m[Glossary]\033[0m"
                print(f"{cyan_glossary} {processed_text}")
            raw_text = processed_text

            # Check if LLM processing is requested by any mode toggle
            needs_llm = self.ui.llm_enabled or self.ui.ai_task_enabled or self.ui.translate_en_enabled
            if needs_llm:
                self.q.put({"cmd": "show", "text": "normalization"})
                final_text = self.llm.normalize(
                    raw_text,
                    translate_en=self.ui.translate_en_enabled,
                    ai_task=self.ui.ai_task_enabled
                )
            else:
                final_text = raw_text
                
            yellow_final = "\033[38;2;255;215;0m\033[1mFinal text:\033[0m"
            print(f"{yellow_final} {final_text}")
            self.typer.type_text(final_text, prepend_clipboard=self.ui.clip_prepend_enabled)
            self.q.put({"cmd": "show_ready"})
        else:
            print("Warning: Transcription was empty or failed. Skipping.")
            self.q.put({"cmd": "show", "text": "what is your command?"})
        
        with self.lock:
            self.is_processing = False
            self.is_recording = False
            self.wake_detector.resume_mic()

    def quit_app(self):
        """Cleanly signals UI to quit."""
        self.q.put({"cmd": "quit"})

    def cleanup(self):
        if hasattr(self, 'wake_detector'):
            self.wake_detector.disable()
        if hasattr(self, 'tray'):
            self.tray.stop()
        if hasattr(self, 'hotkey_mgr'):
            self.hotkey_mgr.stop()
        self.audio.stop_recording()
        if os.path.exists(config.AUDIO_TEMP_FILE):
            try:
                os.remove(config.AUDIO_TEMP_FILE)
            except:
                pass
        release_single_instance()

    def run(self):
        try:
            self.ui.run()
        finally:
            self.cleanup()

if __name__ == "__main__":
    app = WinVoiceApp()
    app.run()
