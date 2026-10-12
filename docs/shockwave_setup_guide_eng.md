# Shockwave — Setup & User Guide

---

## 🚀 Scenario 1. Quick Start (No Python Required)

*Recommended for most users. No Python or additional software installation needed.*

1. **Download the prebuilt archive:**  
   Go to the **[GitHub Releases](https://github.com/mariobr0/shockwave/releases)** page and download **`Shockwave-v0.9.3-Portable.zip`**.
2. **Extract the archive** to any folder (e.g., `C:\Shockwave`).
3. **Run `Shockwave.exe`**:
   * Press **`4`** (`Download / Verify STT Models`) to let the app download Whisper or GigaAM models into the local `models/` folder.
   * Press **`2`** (`Configure API Key & LLM`) if you wish to enable smart punctuation and formatting via an LLM.
4. Press **`1. Start Shockwave`** — the control panel will minimize to the Windows system tray (near clock), and the purple floating widget will appear.
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
git clone https://github.com/mariobr0/shockwave.git
cd shockwave

python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Build `.exe` or Run Directly
* **Build standalone binary:** run **`build.bat`**. The build script generates `dist\Shockwave.exe` and two desktop shortcuts:
  1. **`Shockwave.lnk`** — Control Panel with auto-minimization to system tray.
  2. **`Shockwave (Виджет).lnk`** — Direct silent launch of the floating widget.
* **Direct Python launch:** run **`start.bat`**.

---

## ⚙️ LLM Configuration (Punctuation & Formatting)

| Provider | Endpoint URL (`LLM_ENDPOINT`) | Model Name (`LLM_MODEL`) | API Key Source |
| :--- | :--- | :--- | :--- |
| **Google AI Studio** | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-2.5-flash-lite` | [aistudio.google.com](https://aistudio.google.com/) |
| **OpenAI** | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` | [platform.openai.com](https://platform.openai.com/) |
| **OpenRouter** | `https://openrouter.ai/api/v1/chat/completions` | `google/gemini-2.5-flash-lite` | [openrouter.ai](https://openrouter.ai/) |
| **Ollama (Local)** | `http://localhost:11434/v1/chat/completions` | `qwen2.5:7b` | Not needed (offline) |

External LLM servers require HTTPS. HTTP is allowed only for `localhost` and loopback addresses (`127.0.0.1`, `::1`) on this computer; another computer's HTTP address on the local network is not allowed. Automatic redirects are disabled: use the final API URL. Rejected URLs preserve the original transcript.

If LLM processing fails or returns empty or truncated text, the transcript from before LLM processing is copied to the clipboard and the widget shows `LLM failed: original saved` instead of `ready`. A successful response must contain nonempty text and confirm completion with `finish_reason: stop`; services without that confirmation also fall back to the transcript. If glossary processing fails, text from before substitutions is copied and further LLM processing is skipped. "Saved" means copied to the clipboard, rather than written to a separate file.

---

## 🎛️ Configuration via `config.ini`

User preferences belong in `config.ini` (template: `config.ini.example`). Engine, wake word and language choices made in the menu are saved here. Legacy `.env` preferences remain a fallback when the corresponding setting is absent from `config.ini`. The API key and LLM connection settings remain in `.env`.

* `[Interface] hotkey = ctrl+space` — global system hotkey.
* `[Recognition] whisper_language = ru` — Whisper language (`ru`, `auto`, `en`, etc.).
* `[Recognition] gigaam_quantization = int8` — compressed model; `float32` selects full precision. Matching model files must be downloaded.
* `[Interface] position = bottom-left` — initial widget position.
* `[Interface] opacity = 0.80` — widget opacity.
* `[Toggles] alert_sound = true` — sound notifications.

Write each bracketed section heading on its own line, followed by its settings, as shown in the template. An empty Vosk folder, including one containing only `.gitkeep`, is populated automatically. An incomplete folder containing other files is reported and preserved.

#### Recommended Hotkeys:
* ✅ **Recommended:** `ctrl+space`, `alt+space`, `f9`, `f8`, `f10`, `pause`.
* ⚠️ **Not recommended:** `f12` (reserved by Windows Debugger), `f11` (browser fullscreen), `f5` (page reload).

---

## 🖱️ Widget Controls & System Tray

* **Left grip handle (`⋮⋮`):** Click and drag with mouse to reposition the widget anywhere on your desktop.
* **Shockwave Eye (🟡):** Clickable recording button with visual state indication (glows solid yellow during recording).
* **`LLM norm` checkbox:** Toggle AI-based text punctuation and formatting.
* **`alert` checkbox:** Toggle audio chime notification and startup voice clip.
* **System Tray Icon (near clock):** Double-click to show/hide the console; right-click for quick control menu.
* **Single Instance Protection:** Duplicate launches are automatically prevented without wasting resources.
* **Stopping with the wake word:** All audio is preserved. Only the recognized wake word at the end of the transcript is removed. If recognition does not find it at the end, the transcript is kept unchanged and may still contain the wake word.
* **`×` button:** Exit application.
