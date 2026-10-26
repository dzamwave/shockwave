# Shockwave — Setup & User Guide

---

## 🚀 Scenario 1. Quick Start (No Python Required)

*Recommended for most users. No Python or additional software installation needed.*

1. **Download the prebuilt archive:**
   Go to the **[GitHub Releases](https://github.com/dzamwave/shockwave/releases)** page and download the latest **`Shockwave-v1.1.1-Windows-x64.zip`**.
2. **Extract the archive** to any folder (e.g., `C:\Shockwave`).
3. **Edit `config.ini`** in the `config` folder: engine, wake word, hotkey, and the `[LLM]` section.
4. **Run `Shockwave.exe`**. If the selected model is missing, the program offers to download it and does not change settings. The console then minimizes to the system tray (near the clock), and the purple widget appears.
5. Press **`Ctrl + Space`** in any application to start recording, and press it again to finish. Dictate your speech and paste the result (`Ctrl + V`).

---

## 🛠️ Scenario 2. Build from Source Code

If you prefer to run the project from source or modify the code:

### 1. Requirements
* Windows 10 / 11
* Python 3.10 or newer (make sure to check **Add python.exe to PATH** during installation)
* Git (optional)

### 2. Clone and Install Dependencies
```bat
git clone https://github.com/dzamwave/shockwave.git
cd shockwave

python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Build `.exe` or Run Directly
* **Build standalone binary:** run **`build.bat`**. The build script generates a portable `dist\Shockwave.exe` and two desktop shortcuts:
  1. **`Shockwave.lnk`** — Full launch with console, then auto-minimization to system tray.
  2. **`Shockwave-Widget.lnk`** — Direct silent launch of the floating widget (no console banner).
* **Direct Python launch:** run **`start.bat`** or `python src/launcher.py`.
* **Silent widget launch:** `python src/launcher.py --widget`

---

## ⚙️ LLM Configuration (Punctuation & Formatting)

| Provider | Endpoint URL | Model Name | API Key Source |
| :--- | :--- | :--- | :--- |
| **Google AI Studio** | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-2.5-flash` | [aistudio.google.com](https://aistudio.google.com/) |
| **OpenAI** | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` | [platform.openai.com](https://platform.openai.com/) |
| **OpenRouter** | `https://openrouter.ai/api/v1/chat/completions` | `google/gemini-2.5-flash` | [openrouter.ai](https://openrouter.ai/) |
| **Ollama (Local)** | `http://localhost:11434/v1/chat/completions` | `qwen2.5:7b` | Not needed (offline) |

External LLM servers require HTTPS. HTTP is allowed only for `localhost` and loopback addresses (`127.0.0.1`, `::1`) on this computer; another computer's HTTP address on the local network is not allowed. Automatic redirects are disabled: use the final API URL. Rejected URLs preserve the original transcript.

If LLM processing fails or returns empty or truncated text, the transcript from before LLM processing is copied to the clipboard and the widget shows `LLM failed: original saved` instead of `ready`. A successful response must contain nonempty text and confirm completion with `finish_reason: stop`; services without that confirmation also fall back to the transcript. If glossary processing fails, text from before substitutions is copied and further LLM processing is skipped. "Saved" means copied to the clipboard, rather than written to a separate file.

---

## 🎛️ Configuration via `config.ini`

All settings belong in `config/config.ini` (template: `config/config.example.ini`; the working file is hidden from Git). Startup does not change them. A blank `[LLM]` value is read from `config/.env`. Older recognition values from `.env` are used only when that setting is absent from `config.ini`.

**Key parameters:**

* `[Recording] hotkey = ctrl+space` — global system hotkey.
* `[Recording] max_record_seconds = 180` — recording auto-stop limit (seconds).
* `[Recording] warn_record_seconds = 150` — radar switches to red warning beacon at this point.
* `[Recognition] engine = gigaam_model` — STT engine: `whisper_model` or `gigaam_model`.
* `[Recognition] whisper_language = ru` — Whisper language (`ru`, `auto`, `en`, etc.).
* `[Recognition] gigaam_quantization = int8` — compressed model; `float32` selects full precision.
* `[Recognition] model_idle_timeout = 300` — seconds of inactivity before the STT model is unloaded from RAM (0 = never unload).
* `[Wake] wake = true` — enable or disable wake word detection.
* `[Wake] wake_word = мега` — the trigger phrase listened for in the background.
* `[Text] llm_norm = false` — enable punctuation normalization.
* `[Text] ai_task = false` — enable AI task prompt generation.
* `[Text] to_en = false` — enable translation to English.
* `[Text] idea = false` — enable idea structuring mode.
* `[Text] clip_prepend = false` — prepend dictated text above existing clipboard content.
* `[Widget] position = bottom-right` — initial widget position (`bottom-right`, `bottom-left`, `top-center`).
* `[Widget] opacity = 0.85` — widget opacity (0.0–1.0).
* `[Sound] startup_sound = true` — Megatron voice greeting at launch.
* `[Sound] alert_sound = true` — chime when transcription is ready.
* `[Console] language = ru` — console message language (`ru` / `en`).

Write each bracketed section heading on its own line, followed by its settings, as shown in the template.

#### Recommended Hotkeys:
* ✅ **Recommended:** `ctrl+space`, `alt+space`, `f9`, `f8`, `f10`, `pause`.
* ⚠️ **Not recommended:** `f12` (reserved by Windows Debugger), `f11` (browser fullscreen), `f5` (page reload).

#### Customizing LLM Prompts:
All five system prompts can be edited freely in `config/prompts/`:
`normalization.md`, `translate_en.md`, `ai_task.md`, `ai_task_en.md`, `idea.md`.
Missing files are created automatically with sensible defaults on first launch.
You can also override a prompt inline in `config.ini` under the `[Prompts]` section.

---

## 🖱️ Widget Controls & System Tray

The floating widget has two rows of controls:

**Row 1 (text processing modes):**
* **`LLM norm`** — normalize punctuation and tech terminology via LLM.
* **`AI task`** — convert dictated speech into a structured prompt for an AI assistant. Mutually exclusive with `Idea`.
* **`to EN`** — translate result to English. Combined with `AI task` → single request generating an English AI prompt. Combined with `Idea` → translate after structuring.
* **`Idea`** — structure a free-flowing monologue into a draft publication: key insight, cleaned-up body, and directions to develop. Mutually exclusive with `AI task`.

**Row 2 (recording & clipboard):**
* **`wake`** — enable/disable background wake word listening (Vosk).
* **`alert`** — play a chime when transcription is ready (triggered on wake-word activation and on `show_ready`).
* **`clip+`** — prepend dictated text above existing clipboard content with double newline spacing.

**Other controls:**
* **Radar button (🟡):** Click to start/stop recording. Displays a rotating sweep animation during recording; switches to flashing red when `warn_record_seconds` is exceeded.
* **Countdown timer:** Appears next to the `cancel` button during recording and counts down to the auto-stop limit.
* **`cancel` link:** Immediately discards the active recording without transcribing.
* **`×` button:** Exit application.
* **Drag:** Click and hold anywhere on the widget panel background to reposition it on the desktop.
* **System Tray Icon (near clock):** Right-click for show widget / exit menu.
* **Single Instance Protection:** Duplicate launches are automatically prevented.
* **Stopping with the wake word:** All audio is preserved up to the stop signal. Only the recognized wake word at the end of the transcript is removed. If recognition does not find it at the end, the transcript is kept unchanged.
