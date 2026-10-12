import os
import sys
import subprocess
from dotenv import set_key

# Enable UTF-8 encoding for console output
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ensure modules from src import cleanly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import config

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidate = os.path.join(root_path, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

def get_env_path():
    return config.env_path

def ensure_env_exists():
    env_path = get_env_path()
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("LLM_ENDPOINT=\n")
            f.write("LLM_API_KEY=\n")
            f.write(f"LLM_MODEL={config.LLM_MODEL}\n")

def read_env(key, default=""):
    return getattr(config, key, default)

def update_env(key, value):
    env_path = get_env_path()
    set_key(env_path, key, value)
    os.environ[key] = str(value)
    try:
        setattr(config, key, value)
    except Exception:
        pass

def hex_to_rgb(hex_str, default_rgb):
    try:
        h = str(hex_str).strip().lstrip("#")
        if len(h) == 6:
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        pass
    return default_rgb

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    ansi_path = get_resource_path(os.path.join("icons", "shockwave_transparent.ansi"))
    if os.path.exists(ansi_path):
        try:
            with open(ansi_path, "r", encoding="utf-8") as f:
                lines = f.read().split("\n")
                try:
                    banner_pad_n = int(getattr(config, "CLI_BANNER_PAD", "3"))
                except Exception:
                    banner_pad_n = 3
                pad = " " * max(0, banner_pad_n)
                for line in lines:
                    if line.strip():
                        print(pad + line)
        except Exception:
            pass
            
    # Iconic tagline with configurable color and padding from config / .env
    try:
        quote_pad_n = int(getattr(config, "CLI_QUOTE_PAD", "6"))
    except Exception:
        quote_pad_n = 6
    q_pad = " " * max(0, quote_pad_n)
    
    quote_hex = getattr(config, "CLI_QUOTE_COLOR", "#807785")
    qr, qg, qb = hex_to_rgb(quote_hex, (128, 119, 133))
    tagline = "WHAT IS YOUR COMMAND, MEGATRON?"
    custom_quote = f"\033[1;3;38;2;{qr};{qg};{qb}m{tagline}\033[0m"
    print(f"{q_pad}{custom_quote}\n")

def menu():
    ensure_env_exists()
    
    # Dynamic title color from config / .env (default: #B45FEB)
    title_hex = getattr(config, "CLI_TITLE_COLOR", "#B45FEB")
    tr, tg, tb = hex_to_rgb(title_hex, (180, 95, 235))
    PURPLE = f"\033[38;2;{tr};{tg};{tb}m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    while True:
        clear_screen()
        print_banner()
        
        lang = getattr(config, "APP_LANGUAGE", "ru").lower()
        engine = getattr(config, "STT_ENGINE", "gigaam").lower()
        
        if engine == "whisper":
            whisper_m = getattr(config, "WHISPER_MODEL", "large-v3-turbo")
            stt_display = f"Whisper ({whisper_m})"
        else:
            gigaam_m = getattr(config, "GIGAAM_MODEL", "gigaam-v3-e2e-rnnt")
            quant = getattr(config, "GIGAAM_QUANTIZATION", "int8")
            q_suffix = f", {quant}" if quant else ""
            stt_display = f"GigaAM ({gigaam_m}{q_suffix})"

        wake_word = getattr(config, "WAKE_WORD", "мегатрон")
        wake_display = f"Vosk (\"{wake_word}\")"

        llm_endpoint = getattr(config, "LLM_ENDPOINT", "")
        llm_model = getattr(config, "LLM_MODEL", "gemini-2.5-flash")
        llm_key = getattr(config, "LLM_API_KEY", "")
        version = getattr(config, "APP_VERSION", "1.0.0")
        
        try:
            title_pad_n = int(getattr(config, "CLI_TITLE_PAD", "0"))
        except Exception:
            title_pad_n = 0
        t_pad = " " * max(0, title_pad_n)
        
        # Break URL protocol regex with zero-width space to prevent terminal hyperlink auto-underlining
        safe_endpoint = llm_endpoint.replace("://", ":\u200b//") if llm_endpoint else ""
        
        if lang == "ru":
            endpoint_display = safe_endpoint if safe_endpoint else "НЕ УСТАНОВЛЕН"
            key_display = f"{llm_key[:7]}...{llm_key[-4:]}" if len(llm_key) > 10 else (f"{llm_key[:4]}..." if llm_key else "НЕ УСТАНОВЛЕН")
            print(f"{t_pad}{PURPLE}{BOLD}SHOCKWAVE v{version}{RESET}\n")
            print("Текущие настройки:")
            print(f"- STT Движок:    {stt_display}")
            print(f"- Кодовое слово: {wake_display}")
            print(f"- LLM Эндпоинт:  {endpoint_display}")
            print(f"- LLM Модель:    {llm_model}")
            print(f"- Ключ LLM:      {key_display}\n")
            print("1. Запустить Shockwave")
            print("2. Настроить API-ключ и LLM")
            print("3. Выбрать движок распознавания (STT)")
            print("4. Настроить кодовое слово (Wake Word)")
            print("5. Скачать/Проверить модели распознавания")
            print("6. Change language to English")
            print("7. Выход\n")
            prompt_text = "Ваш выбор (1-7): "
        else:
            endpoint_display = safe_endpoint if safe_endpoint else "NOT SET"
            key_display = f"{llm_key[:7]}...{llm_key[-4:]}" if len(llm_key) > 10 else (f"{llm_key[:4]}..." if llm_key else "NOT SET")
            print(f"{t_pad}{PURPLE}{BOLD}SHOCKWAVE v{version}{RESET}\n")
            print("Current Settings:")
            print(f"- STT Engine:   {stt_display}")
            print(f"- Wake Word:    {wake_display}")
            print(f"- LLM Endpoint: {endpoint_display}")
            print(f"- LLM Model:    {llm_model}")
            print(f"- LLM Key:      {key_display}\n")
            print("1. Start Shockwave")
            print("2. Configure API Key & LLM")
            print("3. Select STT Engine")
            print("4. Configure Wake Word")
            print("5. Download / Verify STT Models")
            print("6. Сменить язык на русский")
            print("7. Exit\n")
            prompt_text = "Your choice (1-7): "
        
        choice = input(prompt_text).strip()
        
        if choice == "1":
            if lang == "ru":
                print("\nПроверка моделей перед запуском...")
            else:
                print("\nChecking models before start...")
                
            import model_manager
            model_manager.check_and_prompt(auto_start=True)
            
            # The model check may have changed the selected engine.
            if config.STT_ENGINE.lower() == "whisper":
                stt_display = f"Whisper ({config.WHISPER_MODEL})"
            else:
                stt_display = f"GigaAM ({config.GIGAAM_MODEL}, {config.GIGAAM_QUANTIZATION})"
            
            if lang == "ru":
                print(f"\nЗапуск Shockwave ({stt_display})...")
                print("Панель управления сворачивается в системный трей (возле часов).")
            else:
                print(f"\nStarting Shockwave ({stt_display})...")
                print("Control panel minimizing to system tray (next to clock).")
                
            import main
            app = main.WinVoiceApp(is_silent=False)
            app.run()
            sys.exit(0)
            
        elif choice == "2":
            setup_llm(lang)
        elif choice == "3":
            setup_stt(lang)
        elif choice == "4":
            setup_wake_word(lang)
        elif choice == "5":
            import model_manager
            model_manager.check_and_prompt(auto_start=False)
            if lang == "ru":
                input("\nНажмите Enter, чтобы вернуться в меню...")
            else:
                input("\nPress Enter to return to menu...")
        elif choice == "6":
            new_lang = "ru" if lang == "en" else "en"
            config.save_setting("APP_LANGUAGE", new_lang)
        elif choice == "7":
            sys.exit(0)

def setup_llm(lang="en"):
    current_endpoint = read_env("LLM_ENDPOINT", "")
    current_key = read_env("LLM_API_KEY", "")
    current_model = read_env("LLM_MODEL", "gemini-2.5-flash-lite")
    
    if lang == "ru":
        print("\n--- Настройка LLM ---")
        print(f"Текущий эндпоинт: {current_endpoint if current_endpoint else 'Отсутствует'}")
        new_endpoint = input("Введите новый URL эндпоинта (или Enter, чтобы оставить): ").strip()
        if new_endpoint:
            update_env("LLM_ENDPOINT", new_endpoint)
            print("Эндпоинт сохранен!")
            
        key_info = f"{current_key[:7]}...{current_key[-4:]}" if len(current_key) > 10 else ("Установлен" if current_key else "Отсутствует")
        print(f"\nТекущий ключ: {key_info}")
        new_key = input("Введите новый API-ключ (или Enter, чтобы оставить): ").strip()
        if new_key:
            update_env("LLM_API_KEY", new_key)
            print("Ключ сохранен!")
            
        print(f"\nТекущая модель: {current_model}")
        new_model = input("Введите название модели (или Enter, чтобы оставить): ").strip()
        if new_model:
            update_env("LLM_MODEL", new_model)
            print("Модель сохранена!")
        input("\nНажмите Enter для возврата...")
    else:
        print("\n--- LLM Settings ---")
        print(f"Current Endpoint: {current_endpoint if current_endpoint else 'Not Set'}")
        new_endpoint = input("Enter new Endpoint URL (or press Enter to keep): ").strip()
        if new_endpoint:
            update_env("LLM_ENDPOINT", new_endpoint)
            print("Endpoint saved!")
            
        key_info = f"{current_key[:7]}...{current_key[-4:]}" if len(current_key) > 10 else ("Set" if current_key else "Not Set")
        print(f"\nCurrent API Key: {key_info}")
        new_key = input("Enter new API Key (or press Enter to keep): ").strip()
        if new_key:
            update_env("LLM_API_KEY", new_key)
            print("API Key saved!")
            
        print(f"\nCurrent Model: {current_model}")
        new_model = input("Enter model name (or press Enter to keep): ").strip()
        if new_model:
            update_env("LLM_MODEL", new_model)
            print("Model saved!")
        input("\nPress Enter to return...")

def setup_stt(lang="en"):
    whisper_m = read_env("WHISPER_MODEL", "large-v3-turbo")
    gigaam_m = read_env("GIGAAM_MODEL", "gigaam-v3-e2e-rnnt")
    
    if lang == "ru":
        print("\n--- Выбор движка распознавания (STT) ---")
        print(f"1. Whisper ({whisper_m}) — отлично для смешанной речи и IT-терминов")
        print(f"2. GigaAM ({gigaam_m}) — очень быстро для русской речи")
        choice = input("\nВыберите движок (1-2): ").strip()
        if choice == "1":
            config.save_setting("STT_ENGINE", "whisper")
            print(f"Установлен движок: Whisper ({whisper_m})")
        elif choice == "2":
            config.save_setting("STT_ENGINE", "gigaam")
            print(f"Установлен движок: GigaAM ({gigaam_m})")
        input("\nНажмите Enter для возврата...")
    else:
        print("\n--- Select STT Engine ---")
        print(f"1. Whisper ({whisper_m}) — great for mixed speech & IT terms")
        print(f"2. GigaAM ({gigaam_m}) — ultra-fast for Russian speech")
        choice = input("\nSelect engine (1-2): ").strip()
        if choice == "1":
            config.save_setting("STT_ENGINE", "whisper")
            print(f"Selected engine: Whisper ({whisper_m})")
        elif choice == "2":
            config.save_setting("STT_ENGINE", "gigaam")
            print(f"Selected engine: GigaAM ({gigaam_m})")
        input("\nPress Enter to return...")

def setup_wake_word(lang="en"):
    current_kw = read_env("WAKE_WORD", "мегатрон")
    
    if lang == "ru":
        print("\n--- Настройка кодового слова (Wake Word) ---")
        print("Модель детектора: Vosk (vosk-model-small-ru)")
        print(f"Текущее кодовое слово: \"{current_kw}\"")
        new_kw = input("\nВведите новое кодовое слово (или Enter, чтобы оставить): ").strip()
        if new_kw:
            config.save_setting("WAKE_WORD", new_kw.lower())
            print(f"Кодовое слово успешно изменено на: \"{new_kw.lower()}\"!")
        input("\nНажмите Enter для возврата...")
    else:
        print("\n--- Wake Word Settings ---")
        print("Detector Model: Vosk (vosk-model-small-ru)")
        print(f"Current Wake Word: \"{current_kw}\"")
        new_kw = input("\nEnter new wake word (or press Enter to keep): ").strip()
        if new_kw:
            config.save_setting("WAKE_WORD", new_kw.lower())
            print(f"Wake word successfully changed to: \"{new_kw.lower()}\"!")
        input("\nPress Enter to return...")

if __name__ == "__main__":
    # Direct silent widget launch via --widget / --silent argument
    if "--widget" in sys.argv or "--silent" in sys.argv:
        from tray_manager import hide_console
        hide_console()
        
        from single_instance import check_single_instance
        if not check_single_instance():
            sys.exit(0)
            
        import main
        app = main.WinVoiceApp(is_silent=True)
        app.run()
        sys.exit(0)
    else:
        # Check single instance before showing interactive Control Panel
        from single_instance import check_single_instance
        if not check_single_instance():
            print("\n[Shockwave] Программа уже запущена! / Shockwave is already running!\n")
            import time
            time.sleep(2.0)
            sys.exit(0)
            
        menu()
