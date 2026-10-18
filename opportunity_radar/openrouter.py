from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenRouterError(RuntimeError):
    """OpenRouter could not return a usable generation."""


def _error_message(exc: HTTPError, api_key: str) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        message = payload.get("error", {}).get("message", "") if isinstance(payload, dict) else ""
    except (UnicodeDecodeError, json.JSONDecodeError):
        message = ""
    return str(message).replace(api_key, "[redacted]")[:500]


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
    urlopen_func: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen_func(request, timeout=timeout) as response:
            decoded = json.load(response)
    except HTTPError as exc:
        detail = _error_message(exc, headers["Authorization"].removeprefix("Bearer "))
        suffix = f": {detail}" if detail else ""
        raise OpenRouterError(f"OpenRouter HTTP {exc.code}{suffix}") from exc
    except TimeoutError as exc:
        raise OpenRouterError("OpenRouter request timed out") from exc
    except URLError as exc:
        raise OpenRouterError("OpenRouter request failed") from exc
    except json.JSONDecodeError as exc:
        raise OpenRouterError("OpenRouter returned malformed JSON") from exc
    if not isinstance(decoded, dict):
        raise OpenRouterError("OpenRouter returned a malformed response")
    return decoded


class OpenRouterClient:
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        model: str = "openrouter/free",
        api_key: str | None = None,
        timeout: int = 120,
        post_json: Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]] = _post_json,
    ):
        if not api_key or not api_key.strip():
            raise OpenRouterError("OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter")
        self.model = model
        self.api_key = api_key.strip()
        self.timeout = max(1, min(timeout, 300))
        self.post_json = post_json
        self.last_content: str | None = None

    def generate(self, prompt: str) -> str:
        response = self.post_json(
            self.endpoint,
            {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            self.timeout,
        )
        if "error" in response:
            message = str(response["error"]).replace(self.api_key, "[redacted]")[:500]
            raise OpenRouterError(f"OpenRouter provider error: {message or 'unknown error'}")
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError("OpenRouter response did not contain message content") from exc
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("OpenRouter response contained empty message content")
        self.last_content = content
        return _clean_json(content)


def _clean_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return text.strip()
