"""Run one non-persistent OpenRouter analysis against a fixed public repository fixture."""

from __future__ import annotations

import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opportunity_radar.analysis import analyze_item, build_prompt
from opportunity_radar.app import RadarConfig
from opportunity_radar.core import normalize_github_item
from opportunity_radar.openrouter import OpenRouterClient


# Static metadata for the public https://github.com/modelcontextprotocol/python-sdk repository.
REPOSITORY_FIXTURE = {
    "id": 0,
    "full_name": "modelcontextprotocol/python-sdk",
    "html_url": "https://github.com/modelcontextprotocol/python-sdk",
    "description": "The official Python SDK for Model Context Protocol servers and clients.",
    "created_at": "2024-11-25T00:00:00Z",
    "updated_at": "2024-11-25T00:00:00Z",
    "pushed_at": "2024-11-25T00:00:00Z",
    "stargazers_count": 0,
    "forks_count": 0,
    "language": "Python",
    "topics": ["mcp", "model-context-protocol", "python"],
    "license": {"spdx_id": "MIT"},
}


def _sanitize(error: Exception, api_key: str | None) -> str:
    message = str(error)
    if api_key:
        message = message.replace(api_key, "[redacted]")
    return message[:500]


def _preview(content: str, api_key: str | None) -> str:
    preview = " ".join(content.split())
    if api_key:
        preview = preview.replace(api_key, "[redacted]")
    preview = re.sub(r"\b(?:sk-or-v1-|sk-)[A-Za-z0-9_-]+", "[redacted]", preview)
    return preview[:500]


def main() -> int:
    config = RadarConfig.from_env()
    item = normalize_github_item(
        REPOSITORY_FIXTURE,
        discovered_at="2026-01-01T00:00:00+00:00",
        query="model context protocol python sdk",
    )
    prompt = build_prompt(item)
    started = time.monotonic()
    print(f"Selected model: {config.openrouter_model}")

    client: OpenRouterClient | None = None
    try:
        client = OpenRouterClient(
            config.openrouter_model,
            config.openrouter_api_key,
            config.openrouter_timeout,
        )

        def generate(analysis_prompt: str) -> str:
            if analysis_prompt != prompt:
                raise RuntimeError("analysis prompt changed before submission")
            return client.generate(analysis_prompt)

        analyze_item(item, generate)
    except Exception as exc:
        print(f"Elapsed time: {time.monotonic() - started:.2f}s")
        print("Schema validation: failed")
        print(f"Error: {_sanitize(exc, config.openrouter_api_key)}")
        if client and client.last_content:
            print(f"Response preview: {_preview(client.last_content, config.openrouter_api_key)}")
        return 1

    print(f"Elapsed time: {time.monotonic() - started:.2f}s")
    print("Schema validation: succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
