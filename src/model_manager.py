import os
import sys
import re
from pathlib import Path

# Suppress Hugging Face warnings
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import config

from huggingface_hub import snapshot_download

WHISPER_REPOS = {
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "large-v3": "Systran/faster-whisper-large-v3",
    "medium": "Systran/faster-whisper-medium",
    "small": "Systran/faster-whisper-small",
    "base": "Systran/faster-whisper-base",
    "tiny": "Systran/faster-whisper-tiny"
}

def is_whisper_downloaded():
    target_dir = config.WHISPER_MODEL_PATH if config.WHISPER_MODEL_PATH else config.WHISPER_DIR
    if os.path.exists(target_dir) and (os.path.exists(os.path.join(target_dir, "model.bin")) or os.path.exists(os.path.join(target_dir, "model.safetensors"))):
        return True
    return False

def is_gigaam_downloaded():
    target_dir = config.GIGAAM_MODEL_PATH if config.GIGAAM_MODEL_PATH else config.GIGAAM_DIR
    folder = Path(target_dir)
    if not folder.is_dir():
        return False
    quant = config.GIGAAM_QUANTIZATION
    suffix = "" if quant in ("", "float32") else "?" + quant
    # Match the file patterns used by onnx-asr for the supported GigaAM versions.
    model = re.fullmatch(r"gigaam-v[23](-e2e)?-(ctc|rnnt)", config.GIGAAM_MODEL.lower())
    if model:
        e2e, architecture = model.groups()
        prefix = "v3_e2e" if e2e else "v?"
        stem = f"{prefix}_{architecture}"
        patterns = ([f"{stem}{suffix}.onnx"] if architecture == "ctc" else
                    [f"{stem}_{part}{suffix}.onnx" for part in ("encoder", "decoder", "joint")])
        patterns.append(f"{stem}_vocab.txt" if e2e else "v?_vocab.txt")
        for pattern in patterns:
            matches = list(folder.glob(pattern))
            if not matches and pattern.endswith(".onnx"):
                matches = list(folder.glob(pattern[:-5] + ".ort"))
            if len(matches) != 1 or not matches[0].is_file() or not matches[0].stat().st_size:
                return False
        return True
    # Preserve custom-model support while distinguishing full and compressed files.
    return any(path.is_file() and path.stat().st_size and
               (("int8" in path.name) == (quant == "int8"))
               for path in folder.glob("*.onnx"))

def download_whisper_direct(whisper_model, lang="en"):
    repo_id = WHISPER_REPOS.get(whisper_model.lower(), whisper_model)
    target_dir = config.WHISPER_MODEL_PATH if config.WHISPER_MODEL_PATH else config.WHISPER_DIR
    os.makedirs(target_dir, exist_ok=True)
    
    msg = f"\nDownloading Whisper ({whisper_model}) directly into {target_dir}..." if lang != "ru" else f"\nСкачивание Whisper ({whisper_model}) напрямую в {target_dir}..."
    print(msg)
    snapshot_download(
        repo_id=repo_id,
        local_dir=target_dir,
        local_dir_use_symlinks=False
    )

def download_gigaam_direct(gigaam_model, quant="int8", lang="en"):
    repo_id = "istupakov/gigaam-v3-onnx"
    target_dir = config.GIGAAM_MODEL_PATH if config.GIGAAM_MODEL_PATH else config.GIGAAM_DIR
    os.makedirs(target_dir, exist_ok=True)
    
    q_str = f" ({quant})" if quant else ""
    msg = f"\nDownloading GigaAM ({gigaam_model}{q_str}) directly into {target_dir}..." if lang != "ru" else f"\nСкачивание GigaAM ({gigaam_model}{q_str}) напрямую в {target_dir}..."
    print(msg)
    
    # If int8 is selected, we only need int8 files + configs to save maximum disk space
    patterns = ["*.json", "*.txt"]
    if quant == "int8":
        patterns.append("*int8*")
    else:
        patterns.append("*.onnx")
        
    snapshot_download(
        repo_id=repo_id,
        local_dir=target_dir,
        allow_patterns=patterns,
        local_dir_use_symlinks=False
    )

def check_and_prompt(auto_start=True):
    whisper_model = config.WHISPER_MODEL
    gigaam_model = config.GIGAAM_MODEL
    engine = config.STT_ENGINE.lower()
    lang = config.APP_LANGUAGE.lower()
    
    needs_download = False
    
    if engine == "whisper" and not is_whisper_downloaded():
        needs_download = True
            
    if engine == "gigaam" and not is_gigaam_downloaded():
        needs_download = True

    if not needs_download:
        if not auto_start:
            if lang == "ru":
                print("\n[OK] Выбранная модель уже скачана и готова к работе!")
            else:
                print("\n[OK] Selected model is already downloaded locally and ready to use!")
        return
        
    if lang == "ru":
        print("\n" + "="*65)
        print("         ПРОВЕРКА И ЗАГРУЗКА МОДЕЛЕЙ РАСПОЗНАВАНИЯ")
        print("="*65)
        print(f"Выбранный движок [{engine.upper()}] не найден в локальной папке.")
        print(f"Файлы будут сохранены напрямую в: \n{config.MODELS_DIR}")
        print("-"*65)
        print("Какую модель вы хотите скачать сейчас?")
        print(f"  1. Только Whisper ({whisper_model}) [~1.5 ГБ] - для IT и смешанной речи")
        print(f"  2. Только GigaAM (gigaam-v3-onnx) [~216 МБ]  - быстрая русская речь")
        print("  3. Скачать обе модели")
        print("  4. Отмена")
        print("="*65)
        prompt_choice = "Ваш выбор (1-4): "
    else:
        print("\n" + "="*65)
        print("           SPEECH RECOGNITION MODEL NOT FOUND")
        print("="*65)
        print(f"Selected engine [{engine.upper()}] is not found locally.")
        print(f"All downloads will be stored directly in: \n{config.MODELS_DIR}")
        print("-"*65)
        print("Which model would you like to download now?")
        print(f"  1. Only Whisper ({whisper_model}) [~1.5 GB] - Best for mixed/IT speech")
        print(f"  2. Only GigaAM (gigaam-v3-onnx) [~216 MB]  - Fast Russian speech")
        print("  3. Download both models")
        print("  4. Cancel")
        print("="*65)
        prompt_choice = "Your choice (1-4): "
    
    while True:
        choice = input(prompt_choice).strip()
        if choice in ["1", "2", "3", "4"]:
            break
        print("Please enter a number from 1 to 4." if lang != "ru" else "Пожалуйста, введите число от 1 до 4.")
        
    if choice == "4":
        if auto_start:
            print("Exiting application..." if lang != "ru" else "Выход из программы...")
            sys.exit(0)
        else:
            return
            
    quant_choice = "int8"
    if choice in ["2", "3"]:
        print("\n" + "-"*65)
        if lang == "ru":
            print("Какую версию для GigaAM вы хотите использовать?")
            print("  1. Сжатая (INT8) ~ 216 МБ (Очень быстрая, рекомендуется)")
            print("  2. Полная (Float32) ~ 885 МБ (Максимальная точность)")
        else:
            print("Which quantization quality for GigaAM would you prefer?")
            print("  1. Compressed (INT8) ~ 216 MB (Ultra-fast, Recommended)")
            print("  2. Full (Float32) ~ 885 MB (Max precision)")
            
        while True:
            q_ans = input("Your choice (1-2): " if lang != "ru" else "Ваш выбор (1-2): ").strip()
            if q_ans in ["1", "2"]:
                break
            print("Enter 1 or 2." if lang != "ru" else "Введите 1 или 2.")
        if q_ans == "2":
            quant_choice = "float32"
            
    if choice in ["1", "3"]:
        download_whisper_direct(whisper_model, lang=lang)
        if choice == "1" and engine != "whisper":
            config.save_setting("STT_ENGINE", "whisper")
            print("Config updated to STT_ENGINE=whisper" if lang != "ru" else "Настройка обновлена: STT_ENGINE=whisper")
            
    if choice in ["2", "3"]:
        download_gigaam_direct(gigaam_model, quant=quant_choice, lang=lang)
        if choice == "2" and engine != "gigaam":
            config.save_setting("STT_ENGINE", "gigaam")
            print("Config updated to STT_ENGINE=gigaam" if lang != "ru" else "Настройка обновлена: STT_ENGINE=gigaam")
            
        config.save_setting("GIGAAM_QUANTIZATION", quant_choice)

    print("\n[OK] All requested models downloaded directly into models/!\n" if lang != "ru" else "\n[OK] Все запрошенные модели успешно скачаны в папку models/!\n")
