from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlencode

from opportunity_radar.sources import SourceError, fetch_json


class CollectionError(RuntimeError):
    """A source could not be collected without risking bad data."""


def _request_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    # Shared fetch: 30s timeout, backoff on 429/5xx; a 403 rate-limit is reported, not retried.
    try:
        payload, _ = fetch_json(url, headers, timeout=30)
    except SourceError as exc:
        raise CollectionError(f"GitHub API: {exc}") from exc
    return payload


def collect_github(
    query: str,
    per_page: int = 10,
    token: str | None = None,
    request_json: Callable[[str, dict[str, str]], dict[str, Any]] = _request_json,
) -> list[dict[str, Any]]:
    search = f"{query} fork:false archived:false"
    params = urlencode({"q": search, "sort": "updated", "order": "desc", "per_page": max(1, min(per_page, 100))})
    url = f"https://api.github.com/search/repositories?{params}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-tech-opportunity-radar/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    payload = request_json(url, headers)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        message = payload.get("message", "missing items") if isinstance(payload, dict) else "non-object response"
        raise CollectionError(f"GitHub API returned malformed search data: {message}")
    return items
