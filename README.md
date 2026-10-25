<p align="center">
  <img src="docs/shockwave.gif" alt="Shockwave">
</p>

# Shockwave

*([Описание на русском ниже](#ru))*

**Shockwave** is an open-source, local-first background voice dictation tool for Windows. It allows you to dictate text completely hands-free via a customizable wake word (powered by Vosk), via a global hotkey, or by clicking the interactive radar button. It automatically normalizes punctuation and tech terminology using an LLM and types/copies the resulting text directly to your focused window.

### Speech Recognition Models:
- **Wake Word Engine (`Vosk`)**: Ultra-lightweight offline acoustic model (`vosk-model-small-ru-0.22`) for continuous background wake word listening with near-zero CPU footprint.
- **Whisper (`large-v3-turbo`)**: State-of-the-art turbo model by OpenAI, optimized for speed. Ideal for mixed English/Russian speech and programming terminology. Runs locally via `faster-whisper`.
- **GigaAM (`gigaam-v3-e2e-rnnt`)**: ONNX version of Sber's GigaAM acoustic model, ported by Ilya Stupakov for fast CPU execution. Runs in `int8` or `float32` format via `onnx-asr`.

### Text Normalization Engine (LLM):
- **OpenAI-compatible endpoint**: Punctuation, idea structuring, AI-task prompts, and English translation. The address, model, and API key come from `[LLM]` in `config.ini`. A blank line falls back to `.env`, then the model name falls back to `gemini-2.5-flash`.

## Features
* **Hands-Free Wake Word (Vosk):** Fully voice-driven recording. Say the wake word from `config.ini` (this copy uses *"шоквейв"*) to start recording, and say it again to stop. The keyword is automatically trimmed from the end of the audio. Change it with `wake_word` in `config.ini`.
* **Rock-Solid System Hotkey:** Native Win32 `RegisterHotKey` (Default `Ctrl + Space`). Never drops out after system sleep, lock screen, or long background sessions.
* **Dynamic Dot-Matrix Radar & Flashing Alert:** Sleek 32×32 px square button with a 5×5 LED micro-pixel matrix featuring a real-time rotating radar sweep and glowing trail during active recording. After `warn_record_seconds` (150 in this copy, about `00:30` left on a 3-minute timer) the radar switches to a flashing red beacon. Click-to-record supported!
* **Live Countdown Timer & Auto-Stop:** Displays remaining recording time (`03:00` → `00:00`) directly on the floating widget next to the `cancel` button. Automatically finalizes recording and submits it to STT at 3 minutes (`max_record_seconds = 180`), protecting ONNX acoustic models from tensor and buffer overflow.
* **Widget Quick Toggles:** Seven switches in two rows: `LLM norm`, `AI task`, `to EN`, `Idea`, `wake`, `alert`, `clip+`. `Idea` and `AI task` turn each other off. With `Idea` and `to EN` together, the text is structured first and then translated. If `LLM norm` is also on, punctuation runs before the idea.
* **AI Task Prompt Generator (`AI task`):** Transforms conversational stream-of-consciousness speech into structured, crystal-clear instructions/prompts for LLMs without chit-chat or filler words.
* **Instant English Translation (`to EN`):** Translates dictated speech directly into natural English with technical term preservation and punctuation restoration.
* **Combined Super-Mode (`AI task` + `to EN`):** When both toggles are enabled, automatically generates structured, production-ready AI directives in English from spoken Russian!
* **Smart Clipboard Prepend (`clip+`):** When enabled, Shockwave prepends your dictated prompt above existing clipboard content (e.g. copied code, errors, or data) with clean double-newline spacing (`Ctrl+V` pastes the full combined prompt!).
* **User Glossary (`glossary.txt`):** Instant dictionary word substitutions immediately after speech recognition. Fully customizable for tech stack, trading terms, or brand names, with hot-reloading on the fly without restarting Shockwave.
* **Dual Speech-to-Text (STT):** Choose between Whisper (mixed IT speech) and GigaAM (ultra-fast Russian speech).
* **Fully Portable & Compact Storage:** Flat directory structure saves weights locally in `models/` with zero bloat (only ~1.76 GB for speech models).
* **Draggable Floating Widget:** Minimalist on-screen overlay. Drag it by the panel itself. The widget stays off the taskbar; Shockwave remains available from the tray icon.
* **Tray Icon:** The console hides to the tray at startup. The tray menu can show it again.
* **Config file:** Engine, wake word, hotkey, widget, and LLM connection are edited in `config.ini`. The program does not ask for them at startup.
* **Safe Configuration Separation:** The working `config/config.ini` is gitignored. The shared template is `config/config.example.ini`, with `endpoint`, `model`, and `api_key` left empty. A blank `[LLM]` value is read from `.env`.
* **Audio Notifications & Startup Sound:** Distinct sound chime plays when transcription is copied and ready. The Megatron startup voice chime can be toggled independently via `startup_sound` in `config.ini`.
* **Safe Terminal Logging:** The console maintains a real-time transcript history to ensure no dictated text is lost.

## Documentation & Installation
Detailed guides are available below:

🇬🇧 **[Setup Guide (English)](docs/shockwave_setup_guide_eng.md)**  
🇷🇺 **[Руководство по настройке (Русский)](docs/shockwave_setup_guide_rus.md)**

---
 
<a id="ru"></a>
# Shockwave

*([English version above](#shockwave))*

**Shockwave** — это легковесный инструмент для голосовой диктовки на Windows, работающий в фоновом режиме. Он позволяет надиктовывать текст полностью без рук с помощью кодового слова (на базе Vosk), по нажатию глобальной горячей клавиши или клику по интерактивной радарной кнопке на панели, автоматически расставляет знаки препинания с помощью нейросети и копирует/вставляет результат прямо в активное окно.

### Модели распознавания речи:
- **Движок кодового слова (`Vosk`)**: Сверхлегковесная локальная модель (`vosk-model-small-ru-0.22`) для непрерывного фонового распознавания кодового слова с минимальной нагрузкой на процессор.
- **Whisper (`large-v3-turbo`)**: Новая турбо-версия большой модели Whisper от OpenAI. Идеальна для смешанной русско-английской речи и IT-терминов. Запускается локально через `faster-whisper`.
- **GigaAM (`gigaam-v3-e2e-rnnt`)**: ONNX-версия нейросети GigaAM от Сбера, портированная Ильей Ступаковым для работы на процессорах. Загружается в версии `int8` или `float32` через `onnx-asr`.

### Движок нормализации текста (LLM):
- **OpenAI-совместимый адрес**: Пунктуация, заготовка идеи, промпт для AI и перевод. Адрес, модель и ключ берутся из секции `[LLM]` в `config.ini`. Пустая строка читается из `.env`, а если имени модели нет и там — используется `gemini-2.5-flash`.

## Возможности
* **Голосовая активация без рук (Hands-Free на базе Vosk):** Управляйте записью только голосом. Произнесите кодовое слово из `config.ini` (в этой копии — *«шоквейв»*) для старта и повторите его для завершения. Стоп-слово вырезается из конца записи. Слово меняется параметром `wake_word` в `config.ini`.
* **Надёжная системная горячая клавиша:** Работает через ядро Windows (`RegisterHotKey`, по умолчанию `Ctrl + Space`). Никогда не отваливается после сна или блокировки экрана.
* **Интерактивный матричный радар с индикацией тревоги:** Кнопка 32×32 px со светодиодной матрицей 5×5 и вращающимся лучом во время записи. После `warn_record_seconds` (в этой копии 150 секунд, на трёхминутном таймере это около `00:30`) радар мигает красным. Диктовку можно начать кликом.
* **Таймер обратного отсчета и автостоп:** В режиме записи рядом с кнопкой `cancel` отображается точный обратный отсчет (`03:00` → `00:00`). По истечении 3 минут (`max_record_seconds = 180`) запись автоматически завершается и передается на распознавание, предотвращая переполнение буфера нейросетей ONNX.
* **Быстрые тумблеры на виджете:** Семь переключателей в два ряда: `LLM norm`, `AI task`, `to EN`, `Idea`, `wake`, `alert` и `clip+`. `Idea` и `AI task` выключают друг друга. Если вместе включены `Idea` и `to EN`, текст сначала структурируется, потом переводится. Если ещё включена нормализация, она идёт первым шагом.
* **Генератор инструкций для AI (`AI task`):** Превращает устный поток мыслей в чёткие, структурированные промпты для нейросетей без лишних разговорных междометий и слов-паразитов.
* **Мгновенный перевод на английский (`to EN`):** Переводит надиктованную речь на естественный английский язык с сохранением технической терминологии и знаков препинания.
* **Супер-режим (`AI task` + `to EN`):** При одновременном включении обоих чекбоксов Shockwave формирует профессиональный англоязычный промпт для AI прямо из русской устной речи!
* **Умное дополнение буфера (`clip+`):** Если включен тумблер `clip+` и в буфере уже скопирован фрагмент кода или текст, Shockwave вставит надиктованный промпт над содержимым буфера через две пустые строки (по `Ctrl+V` сразу вставляется готовый запрос с контекстом!).
* **Пользовательский словарь (`glossary.txt`):** Мгновенная замена специфических терминов и названий прямо после распознавания. Поддерживает редактирование на лету без перезапуска программы.
* **Два движка распознавания (STT):** Быстрый выбор между Whisper (для смешанной IT-речи) и GigaAM (очень быстрый для русской речи).
* **Полная портативность и компактность:** Оптимизированная структура хранения моделей в `models/` без дубликатов (всего ~1.76 ГБ для речевых моделей).
* **Перемещаемый виджет:** Плашку можно перетащить за саму панель. С панели задач она скрыта. Программа остаётся в трее у часов.
* **Иконка в трее:** При старте консоль прячется в трей. Из меню трея её можно показать снова.
* **Файл настроек:** Движок, кодовое слово, горячая клавиша, виджет и подключение LLM задаются в `config.ini`. При запуске программа их не спрашивает.
* **Чёткое разделение настроек:** Рабочий `config/config.ini` скрыт от Git. В репозитории лежит шаблон `config/config.example.ini`: те же параметры, но `endpoint`, `model` и `api_key` пустые. Пустое поле `[LLM]` читается из `.env`.
* **Гибкая настройка звука:** Приветствие Мегатрона при старте можно независимо отключить параметром `startup_sound = false` в `config.ini`, сохранив приятные сигналы готовности текста.
* **Бекап-лог:** Консоль сохраняет лог и всю историю расшифровок в рамках открытой сессии.

## Документация и Установка
Подробные инструкции по установке:

🇬🇧 **[Setup Guide (English)](docs/shockwave_setup_guide_eng.md)**  
🇷🇺 **[Руководство по настройке (Русский)](docs/shockwave_setup_guide_rus.md)**

---

<p align="center">
  <img src="docs/control_panel.png?v=1.0.1" alt="Control Panel" width="753">
  <br><br>
  <img src="docs/floating_widget.png?v=1.0.1" alt="Floating Widget" width="521">
</p>
