from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """Ollama could not return a usable generation."""


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        raise OllamaError(f"Ollama HTTP {exc.code}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OllamaError(f"Ollama request failed: {exc}") from exc


class OllamaClient:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: int = 180,
        think: bool = False,
        post_json: Callable[[str, dict[str, Any], int], dict[str, Any]] = _post_json,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.think = think
        self.post_json = post_json

    def generate(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 1024},
        }
        if not self.think:
            payload["think"] = False
        response = self.post_json(f"{self.base_url}/api/generate", payload, self.timeout)
        generated = response.get("response") if isinstance(response, dict) else None
        if not isinstance(generated, str) or not generated.strip():
            generated = response.get("thinking") if isinstance(response, dict) else None
        if not isinstance(generated, str) or not generated.strip():
            raise OllamaError("Ollama response did not contain generated text")
        # Strip potential markdown fences if present
        text = generated.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # If model adds preamble or trailing text, extract the outermost JSON object
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]
        return text.strip()

