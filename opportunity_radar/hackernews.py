from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlencode

from opportunity_radar.sources import SourceError, canonical_url, fetch_json


class HackerNewsError(RuntimeError):
    """Raised when Hacker News API cannot be collected."""


def _request_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    try:
        payload, _ = fetch_json(url, headers)  # timeout + backoff on 429/5xx
    except SourceError as exc:
        raise HackerNewsError(f"Hacker News API: {exc}") from exc
    return payload


DEFAULT_HN_QUERIES = (
    "Show HN AI",
    "AI agent",
    "MCP server",
    "local LLM",
    "AI automation",
)


def collect_hackernews(
    query: str,
    per_page: int = 10,
    request_json: Callable[[str, dict[str, str]], dict[str, Any]] = _request_json,
    min_points: int = 0,
) -> list[dict[str, Any]]:
    """
    Collects stories from Hacker News via the free public Algolia search API.
    Does not require any API key or subscription.
    """
    params = {
        "query": query,
        "tags": "(story,show_hn)",
        "hitsPerPage": max(1, min(per_page, 50)),
    }
    if min_points > 0:
        params["numericFilters"] = f"points>={min_points}"
    url = f"https://hn.algolia.com/api/v1/search_by_date?{urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "ai-tech-opportunity-radar/0.3",
    }
    payload = request_json(url, headers)
    hits = payload.get("hits") if isinstance(payload, dict) else None
    if not isinstance(hits, list):
        raise HackerNewsError("Hacker News API returned non-list hits")
    return hits


def _hn_type(title: str, url: str, default: str) -> str:
    lowered = title.lower()
    if lowered.startswith("ask hn"):
        return "business"  # discussions that surface unmet needs
    if url.startswith("https://github.com/"):
        return "open_source"
    if lowered.startswith("show hn"):
        return "product_tool"
    return default


def normalize_hn_item(hit: dict[str, Any], discovered_at: str, query: str, item_type: str = "business") -> dict[str, Any]:
    """Normalizes an Algolia HN hit into the common radar item structure."""
    object_id = str(hit.get("objectID") or "")
    discussion_url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""
    external_url = hit.get("url") or discussion_url
    title = str(hit.get("title") or "Untitled Hacker News Item").strip()
    story_text = str(hit.get("story_text") or "").strip()

    return {
        "source_id": f"hn:{object_id}",
        "title": title,
        "source": "Hacker News",
        "url": external_url,
        "canonical_url": canonical_url(external_url),
        "item_type": _hn_type(title, canonical_url(external_url), item_type),
        "date_discovered": discovered_at,
        "raw_description": story_text if story_text else title,
        "author": hit.get("author") or "",
        "published_at": hit.get("created_at"),
        "created_at": hit.get("created_at"),
        "updated_at": hit.get("created_at"),
        "pushed_at": hit.get("created_at"),
        "topics": ["hacker-news", query.lower().replace(" ", "-")],
        "language": None,
        "archived": False,
        "fork": False,
        "evidence": {
            "points": int(hit.get("points") or 0),
            "comments": int(hit.get("num_comments") or 0),
            "author": hit.get("author") or "",
            "discussion_url": discussion_url,
            "query": query,
            "source_updated_at": hit.get("created_at"),
        },
    }
