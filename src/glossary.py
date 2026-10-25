import os
import sys
import re

DEFAULT_GLOSSARY_TEMPLATE = """# Shockwave Glossary / Пользовательский словарь замен
# Формат: шаблон = замена (регистронезависимо, по границам слов)
# Файл можно редактировать на лету — изменения подхватываются автоматически без перезапуска Shockwave.
# Строки с решеткой (#) или пустые строки игнорируются.

# --- 1. Контекст диалога, проекта и AI-инструментов ---
шоквейв = Shockwave
тайгер трейд = Tiger.Trade
антигравити = Antigravity
вайб кодинг = Vibe Coding
вайбкодинг = Vibe Coding
джемини = Gemini
гигаам = GigaAM
воск = Vosk
виспер = Whisper
пайинсталлер = PyInstaller
венв = venv

# --- 2. Разработка, языки и инфраструктура ---
докер = Docker
кубер = Kubernetes
кубернетес = Kubernetes
гит = Git
гитхаб = GitHub
гитлаб = GitLab
питон = Python
си шарп = C#
сишарп = C#
тайпскрипт = TypeScript
джаваскрипт = JavaScript
реакт = React
постгрес = PostgreSQL
редис = Redis
линукс = Linux
виндоус = Windows
эндпоинт = endpoint
вебсокет = WebSocket
джейсон = JSON
пайплайн = pipeline
пулл реквест = Pull Request
пулреквест = Pull Request
мердж = Merge
деплой = Deploy
рефакторинг = рефакторинг
бэкенд = Backend
фронтенд = Frontend
фуллстек = Fullstack
апи = API
баг = баг

# --- 3. Искусственный интеллект и LLM ---
промпт = промпт
ллм = LLM
токен = токен
инференс = Inference
эмбеддинг = Embedding
файнтьюнинг = Fine-tuning
вейкворд = Wake Word

# --- 4. Трейдинг, крипта и биржевой анализ ---
бинанс = Binance
байбит = Bybit
окейикс = OKX
юсдт = USDT
тезер = USDT
биткоин = Bitcoin
биток = Bitcoin
эфир = Ethereum
эфириум = Ethereum
солана = Solana
стоплосс = Stop Loss
стоп лосс = Stop Loss
тейкпрофит = Take Profit
тейк профит = Take Profit
тейк = Take Profit
лимитка = лимитный ордер
ордербук = Order Book
футпринт = Footprint
кумулятивная дельта = кумулятивная дельта
таймфрейм = таймфрейм
ликвидация = ликвидация
волатильность = волатильность
"""

class GlossaryManager:
    def __init__(self, glossary_path=None):
        if glossary_path is None:
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
                self.glossary_path = os.path.join(exe_dir, "glossary.txt")
            else:
                self.glossary_path = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "glossary.txt")
                )
        else:
            self.glossary_path = glossary_path

        self._last_mtime = None
        self._rules = []
        self._ensure_file_exists()
        self.reload()

    def _ensure_file_exists(self):
        """Creates a default glossary.txt template if the file doesn't exist yet."""
        if not os.path.exists(self.glossary_path):
            try:
                with open(self.glossary_path, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_GLOSSARY_TEMPLATE)
            except Exception as e:
                print(f"[Glossary] Error creating default glossary file: {e}")

    def reload(self):
        """Parses glossary.txt and compiles regex patterns if the file was modified."""
        if not os.path.exists(self.glossary_path):
            self._rules = []
            return

        try:
            mtime = os.path.getmtime(self.glossary_path)
            if self._last_mtime is not None and mtime == self._last_mtime:
                return

            rules = []

            with open(self.glossary_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        pattern, replacement = line.split("=", 1)
                        pattern = pattern.strip()
                        replacement = replacement.strip()
                        if pattern and replacement:
                            rules.append((pattern, replacement))

            # Sort rules by pattern length descending to replace longer phrases first
            rules.sort(key=lambda r: len(r[0]), reverse=True)

            compiled_rules = []
            for pattern, replacement in rules:
                # Use unicode-safe word boundaries (?<!\w) and (?!\w)
                regex = re.compile(
                    r'(?<!\w)' + re.escape(pattern) + r'(?!\w)',
                    re.IGNORECASE | re.UNICODE
                )
                compiled_rules.append((regex, replacement))

            self._rules = compiled_rules
            self._last_mtime = mtime
            print(f"[Glossary] Loaded {len(self._rules)} rules from {self.glossary_path}")
        except Exception as e:
            print(f"[Glossary] Error reading glossary file: {e}")

    def apply(self, text: str) -> str:
        """Applies glossary substitution rules to text."""
        if not text:
            return text

        self.reload()
        if not self._rules:
            return text

        result = text
        for regex, replacement in self._rules:
            # Callable replacements are literal: backslashes are not regex commands.
            result = regex.sub(lambda match: replacement, result)

        return result
