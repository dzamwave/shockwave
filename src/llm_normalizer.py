import requests
import config
import ipaddress
from urllib.parse import urlsplit
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizationResult:
    text: str
    succeeded: bool
    warning: str = ""


def _validated_endpoint(value):
    """Require TLS except for an explicit loopback destination."""
    endpoint = value.strip()
    if "\\" in endpoint or any(char.isspace() or ord(char) < 32 for char in endpoint):
        raise ValueError("Некорректный адрес LLM-сервера.")
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname
        port = parsed.port  # Reject invalid ports before sending anything.
        if not host or parsed.scheme not in ("https", "http") or port == 0:
            raise ValueError
        if parsed.username is not None or parsed.password is not None:
            raise ValueError
    except ValueError:
        raise ValueError("Некорректный адрес LLM-сервера: нужен HTTP или HTTPS без логина в URL.") from None
    if parsed.scheme == "http":
        local = host == "localhost"
        if not local:
            try:
                local = ipaddress.ip_address(host).is_loopback
            except ValueError:
                local = False
        if not local:
            raise ValueError("Внешний LLM-сервер требует HTTPS. HTTP разрешён только на этом компьютере.")
    return endpoint

def _processing_steps(translate_en, ai_task, idea, normalize):
    """Idea runs after punctuation and before English. Other modes stay one request."""
    if idea:
        steps = []
        if normalize:
            steps.append("normalize")
        steps.append("idea")
        if translate_en:
            steps.append("translate")
        return steps
    if translate_en and ai_task:
        return ["ai_task_en"]
    if ai_task:
        return ["ai_task"]
    if translate_en:
        return ["translate"]
    return ["normalize"]

def _step_prompt(step):
    if step == "idea":
        return getattr(config, "LLM_PROMPT_IDEA", config.DEFAULT_IDEA_PROMPT), "Structuring idea", 2048
    if step == "ai_task_en":
        return getattr(config, "LLM_PROMPT_AI_TASK_EN", config.DEFAULT_AI_TASK_EN_PROMPT), "Generating AI task (EN)", 1024
    if step == "ai_task":
        return getattr(config, "LLM_PROMPT_AI_TASK", config.DEFAULT_AI_TASK_PROMPT), "Generating AI task", 1024
    if step == "translate":
        return getattr(config, "LLM_PROMPT_TRANSLATE_EN", config.DEFAULT_TRANSLATE_EN_PROMPT), "Translating to EN", 1024
    return config.STT_SYSTEM_PROMPT, "Normalizing", 1024

class LLMNormalizer:
    def normalize(self, text, translate_en=False, ai_task=False, idea=False, normalize=False):
        """Keep the text-only API for callers that do not display processing status."""
        return self.normalize_result(
            text, translate_en=translate_en, ai_task=ai_task, idea=idea, normalize=normalize
        ).text

    def normalize_result(self, text, translate_en=False, ai_task=False, idea=False, normalize=False):
        if not text:
            return NormalizationResult("", True)

        red = "\033[38;2;231;76;60m"
        reset = "\033[0m"

        if not config.LLM_ENDPOINT:
            print(f"{red}Notice: LLM Endpoint is not configured. Returning raw transcript.{reset}")
            return NormalizationResult(text, False, "LLM-сервер не настроен.")

        try:
            endpoint = _validated_endpoint(config.LLM_ENDPOINT)
        except ValueError as e:
            print(f"{red}LLM: {e} Исходный текст сохранён.{reset}")
            return NormalizationResult(text, False, str(e))

        headers = {"Content-Type": "application/json"}
        if config.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"

        current = text
        for step in _processing_steps(translate_en, ai_task, idea, normalize):
            result = self._apply_step(endpoint, headers, current, step)
            if not result.succeeded:
                return NormalizationResult(text, False, result.warning)
            current = result.text
        return NormalizationResult(current, True)

    def _apply_step(self, endpoint, headers, text, step):
        red = "\033[38;2;231;76;60m"
        reset = "\033[0m"
        system_prompt, action_name, max_tokens = _step_prompt(step)
        user_prompt = f"Raw transcript to process:\n{text}"
        model_name = getattr(config, "LLM_MODEL", "gemini-2.5-flash-lite")
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1
        }

        print(f"{action_name} with {model_name}... ", end="", flush=True)
        
        timeout_sec = getattr(config, "LLM_TIMEOUT", 25)
        try:
            options = {"allow_redirects": False}
            if urlsplit(endpoint).scheme == "http":
                # A local plaintext request must not go through an external
                # proxy inherited from the process environment.
                options["proxies"] = {"http": "", "https": "", "all": ""}
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_sec, **options)
            if 300 <= response.status_code < 400:
                print(f"{red}LLM: перенаправление отклонено. Укажите конечный адрес сервера.{reset}")
                return NormalizationResult(text, False, "Перенаправление LLM отклонено.")
            if not response.ok:
                err_detail = ""
                try:
                    err_json = response.json()
                    err_detail = err_json.get("error", {}).get("message") or str(err_json)
                except Exception:
                    err_detail = response.text.strip()[:200]
                print(f"{red}Failed (HTTP {response.status_code}: {err_detail}){reset}")
                return NormalizationResult(text, False, f"Ошибка LLM: HTTP {response.status_code}.")
                
            data = response.json()
            choices = data.get("choices") if isinstance(data, dict) else None
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError("Некорректный ответ LLM.")
            choice = choices[0]
            reason = choice.get("finish_reason")
            if reason != "stop":
                warning = "Ответ LLM обрезан." if reason == "length" else "Завершение ответа LLM не подтверждено."
                print(f"{red}Failed ({warning} Исходный текст сохранён.){reset}")
                return NormalizationResult(text, False, warning)
            message = choice.get("message")
            if not isinstance(message, dict) or message.get("refusal"):
                return NormalizationResult(text, False, "LLM не вернул готовый текст.")
            normalized = message.get("content")
            if isinstance(normalized, str) and normalized.strip():
                # Guardrail: detect provider warning/error messages returned under HTTP 200
                suspicious_phrases = [
                    "is no longer available",
                    "please switch to",
                    "model is deprecated",
                    "model not found"
                ]
                lower_norm = normalized.lower()
                lower_orig = text.lower()
                detected = next((p for p in suspicious_phrases if p in lower_norm and p not in lower_orig), None)
                if detected:
                    clean_msg = normalized.replace("\n", " ").strip()[:90]
                    print(f"{red}Failed (Provider: {clean_msg}){reset}")
                    return NormalizationResult(text, False, "Сервис LLM не выполнил обработку.")
                    
                print("Success")
                return NormalizationResult(normalized.strip(), True)
            else:
                print(f"{red}Failed (Model returned empty response){reset}")
                return NormalizationResult(text, False, "LLM вернул пустой или некорректный текст.")
                
        except requests.exceptions.Timeout:
            print(f"{red}Failed (Connection timeout: server did not respond within {timeout_sec}s){reset}")
            return NormalizationResult(text, False, "Время ожидания LLM истекло.")
        except requests.exceptions.ConnectionError:
            print(f"{red}Failed (Connection error: unable to reach endpoint {config.LLM_ENDPOINT}){reset}")
            return NormalizationResult(text, False, "Не удалось подключиться к LLM.")
        except requests.exceptions.RequestException as e:
            print(f"{red}Failed ({e}){reset}")
            return NormalizationResult(text, False, "Ошибка запроса к LLM.")
        except Exception as e:
            print(f"{red}Failed ({e}){reset}")
            return NormalizationResult(text, False, "Некорректный ответ или ошибка обработки LLM.")
