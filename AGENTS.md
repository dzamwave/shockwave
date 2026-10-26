# Shockwave — Project Context (Level 1)

> **Локальный путь:** `C:\Users\dzam\Desktop\VibeCoding\Shockwave`  
> **Стек:** Python 3.12, Faster-Whisper, Vosk, ONNX Runtime (GigaAM), SoundDevice, Win32 API (`RegisterHotKey`), PyInstaller  
> **Интерпретатор:** `.\venv\Scripts\python.exe`  
> **Версия приложения:** `1.1.1`  
> **Конфигурация:** `config/config.ini` (рабочий файл, в gitignore), `config/config.example.ini` (шаблон с пустыми `endpoint`, `model`, `api_key`), `config/.env` (запас для пустых полей `[LLM]`), `config/prompts/*.md` (системные промпты)

---

## 1. Назначение и возможности

Локальная система голосовой диктовки без рук для Windows, работающая в фоновом режиме:
1. **Hands-Free активация (Vosk):** Фоновое распознавание кодового слова. Слово задаётся параметром `wake_word` в секции `[Wake]` `config.ini` (дефолт — `мега`). Кодовое слово автоматически вырезается из конца записи после распознавания.
2. **Системный хоткей:** Нативный Win32 `RegisterHotKey` (по умолчанию `Ctrl + Space`), устойчив ко сну и экрану блокировки. Задаётся параметром `hotkey` в `[Recording]`.
3. **Распознавание речи (STT):**
   * **Whisper (`large-v3-turbo`):** Локальная инференс-модель для смешанной речи (RU/EN) и терминов программирования. Язык задаётся `whisper_language`.
   * **GigaAM (`gigaam-v3-e2e-rnnt`):** ONNX-модель от Сбера для скоростного распознавания русской речи на CPU. Квантизация задаётся `gigaam_quantization` (`int8` / `float32`).
   * **Ленивая загрузка:** STT-модель загружается в память при первом запросе, а не при старте. Выгружается фоновым watchdog-потоком после `model_idle_timeout` секунд простоя (по умолчанию 300 с; 0 — не выгружать). Preload запускается асинхронно в момент начала записи.
4. **LLM-обработка** (OpenAI-совместимый endpoint, `[LLM]` в `config.ini`):
   * `LLM norm` — нормализация пунктуации и форматирование терминологии.
   * `Idea` — структурирует поток мыслей в заготовку для поста: выделяет главную мысль, убирает мусор, сохраняет стиль автора.
   * `AI task` — превращает устную речь в чёткий структурированный промпт для AI. Взаимоисключает `Idea`.
   * `to EN` — перевод на английский. Вместе с `AI task` → `AI task (EN)` (один запрос). Вместе с `Idea` → перевод после структурирования.
   * Если включены `LLM norm` + `Idea` + `to EN`, цепочка запросов: нормализация → идея → перевод.
   * Адрес, ключ и модель читаются из `LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_MODEL`. Дефолтная модель — `gemini-2.5-flash`. Пустые поля `[LLM]` берутся из `config/.env`.
   * HTTP разрешён только на loopback; внешние серверы требуют HTTPS. Перенаправления (3xx) отклоняются. Подозрительные ответы провайдера (deprecation, not found) определяются по guardrail-фразам.
5. **Интерфейс:** Плавающий радар-виджет (Dot-Matrix Radar 32×32 px, матрица 5×5 LED), тулбар с тумблерами в 2 ряда × 4 колонки, системный трей.
6. **Watchdog записи:** При превышении `warn_record_seconds` (дефолт 150 с) радар переключается в мигающий красный режим. При достижении `max_record_seconds` (дефолт 180 с) запись автоматически завершается.

---

## 2. Ключевые файлы (`src/` и корень)

* `src/launcher.py` — Точка входа. Выводит ANSI-баннер, читает движок из `config.ini`, запускает `model_manager.ensure_configured_model()`, затем `main.WinVoiceApp`. Флаги `--widget` / `--silent` — бесшумный старт без баннера.
* `src/main.py` — Оркестратор: сборка компонентов, очередь UI-команд, обработка записи, LLM-пайплайн, буфер обмена, корректный выход с освобождением ресурсов.
* `src/audio_engine.py` — Захват звука (`sounddevice`), буфер фреймов, ленивая загрузка/выгрузка STT-модели, idle watchdog, транскрипция Whisper и GigaAM.
* `src/wake_word.py` — Vosk wake word: очередь аудио-чанков → фоновый поток распознавания → callback `on_wake_callback`. Методы `enable` / `disable` / `pause_mic` / `resume_mic`.
* `src/model_manager.py` — Проверка наличия весов Whisper/GigaAM, скачивание с HuggingFace Hub при их отсутствии (интерактивный запрос y/n). Паттерны glob учитывают квантизацию и форматы `.onnx` / `.ort`.
* `src/llm_normalizer.py` — Цепочка LLM-запросов: `_processing_steps()` определяет шаги по флагам, `_apply_step()` отправляет один запрос. Валидация endpoint (TLS, loopback, запрет редиректов). `NormalizationResult(text, succeeded, warning)`.
* `src/hotkey_manager.py` — Глобальная клавиша Win32 `RegisterHotKey`; запасной вариант — библиотека `keyboard`.
* `src/ui.py` — Плавающий оверлей (tkinter, `overrideredirect`). Радар: вращающийся луч с trail-затуханием (`_radar_tick` каждые 35 мс). Тумблеры: `LLM norm`, `AI task`, `to EN`, `Idea` (ряд 0); `wake`, `alert`, `clip+` (ряд 1). Countdown-таймер. `WS_EX_TOOLWINDOW` — скрыт из taskbar. `enforce_topmost` вызывается каждые 10 очередных тиков (~1 с).
* `src/tray_manager.py` — Иконка у часов, меню «Показать / Выход», показ и скрытие консоли.
* `src/glossary.py` — Автозамены из `glossary.txt` с hot-reload при изменении файла (watchdog по mtime).
* `src/typer.py` — Кладёт готовый текст в буфер обмена (`pyperclip`). При `clip_prepend=True` — prepend над существующим содержимым буфера через `\n\n`. Клавиши не нажимает.
* `src/config.py` — Чтение `config.ini` → `.env` → дефолт. Секции: `[Recording]`, `[Recognition]`, `[Wake]`, `[Text]`, `[LLM]`, `[Prompts]`, `[Widget]`, `[Sound]`, `[Console]`. `save_setting()` — атомарная запись через tempfile. `get_prompt()` — приоритет: `[Prompts]` → `config/prompts/*.md` → встроенный дефолт.
* `src/single_instance.py` — Один запущенный процесс через именованный mutex Windows.
* `start.bat` — Запуск из виртуального окружения.
* `build.bat` — Сборка EXE через PyInstaller.
* `make_shortcuts.py` — Создание `.lnk`-ярлыков (Shockwave.lnk, Shockwave-Widget.lnk).

---

## 3. Секции `config.ini` и ключевые параметры

| Секция | Параметр | Дефолт | Описание |
|--------|----------|--------|----------|
| `[Recording]` | `hotkey` | `ctrl+space` | Глобальная горячая клавиша |
| `[Recording]` | `max_record_seconds` | `180` | Автостоп записи |
| `[Recording]` | `warn_record_seconds` | `150` | Предупреждение (красный радар) |
| `[Recognition]` | `engine` | `gigaam_model` | `whisper_model` или `gigaam_model` |
| `[Recognition]` | `whisper_model` | `large-v3-turbo` | Имя модели Whisper |
| `[Recognition]` | `whisper_language` | `ru` | Язык (`auto`/`none` → autodetect) |
| `[Recognition]` | `gigaam_model` | `gigaam-v3-e2e-rnnt` | Имя модели GigaAM |
| `[Recognition]` | `gigaam_quantization` | `int8` | `int8` или `float32` |
| `[Recognition]` | `model_idle_timeout` | `300` | Секунды до выгрузки модели (0 = нет) |
| `[Recognition]` | `onnx_optimize_memory` | `true` | ONNX арена памяти отключена |
| `[Wake]` | `wake` | `true` | Включить wake word |
| `[Wake]` | `wake_word` | `мега` | Кодовое слово |
| `[Text]` | `llm_norm` | `false` | Нормализация пунктуации |
| `[Text]` | `ai_task` | `false` | Генерация промпта для AI |
| `[Text]` | `to_en` | `false` | Перевод на английский |
| `[Text]` | `idea` | `false` | Структурирование идеи |
| `[Text]` | `clip_prepend` | `false` | Prepend над буфером обмена |
| `[LLM]` | `endpoint` | `""` | URL OpenAI-совместимого API |
| `[LLM]` | `model` | `gemini-2.5-flash` | Модель LLM |
| `[LLM]` | `api_key` | `""` | API-ключ |
| `[LLM]` | `timeout` | `25` | Таймаут запроса (секунды) |
| `[Widget]` | `position` | `bottom-right` | Позиция виджета |
| `[Widget]` | `opacity` | `0.85` | Прозрачность виджета |
| `[Sound]` | `startup_sound` | `true` | Звук Megatron при старте |
| `[Sound]` | `alert_sound` | `true` | Звук готовности текста |
| `[Console]` | `language` | `ru` | Язык сообщений (`ru` / `en`) |

Промпты (приоритет: `[Prompts]` в `config.ini` → файл `config/prompts/*.md` → встроенный дефолт):
`normalization.md`, `translate_en.md`, `ai_task.md`, `ai_task_en.md`, `idea.md`

---

## 4. Команды запуска и сборки

```bash
# Запуск
start.bat
# или
python src/launcher.py

# Сразу виджет, без приветствия в терминале
python src/launcher.py --widget

# Сборка дистрибутива
build.bat
```

---

## 5. Инварианты проекта

1. **Разделение конфигов:** рабочий `config/config.ini` скрыт от Git. В репозитории лежит `config/config.example.ini`: те же настройки, но `endpoint`, `model` и `api_key` пустые. Пустое поле `[LLM]` берётся из `config/.env`. Тексты промптов — в `config/prompts/*.md`.
2. **Буфер обмена:** `typer.py` только копирует текст. Активное окно не переключается, потому что программа не эмулирует нажатия клавиш.
3. **Безопасность LLM:** HTTP разрешён только на loopback-адресах; внешние LLM-серверы требуют HTTPS. Редиректы (3xx) блокируются. Учётные данные не встраиваются в URL.
4. **Взаимоисключение режимов:** `Idea` и `AI task` не могут быть включены одновременно — включение одного автоматически отключает другой.
5. **Watchdog и гонки:** `_audio_lock` (RLock) защищает все операции с устройством. `lock` (Lock) защищает флаги состояния. Оба не держатся одновременно в callback-потоках. `_recording_id` инвалидирует устаревшие воркеры.
6. **Ответы агента:** На русском языке, лаконично.
