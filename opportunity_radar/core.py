from __future__ import annotations

import re
from difflib import SequenceMatcher
from math import log1p
from typing import Any

from opportunity_radar.sources import canonical_url


def normalize_github_item(raw: dict[str, Any], discovered_at: str, query: str) -> dict[str, Any]:
    license_data = raw.get("license") or {}
    owner = raw.get("owner") or {}
    return {
        "source_id": f"github:{raw['id']}",
        "title": raw.get("full_name") or raw.get("name") or "Untitled repository",
        "source": "GitHub",
        "url": raw.get("html_url", ""),
        "canonical_url": canonical_url(raw.get("html_url", "")),
        "item_type": "open_source",
        "date_discovered": discovered_at,
        "raw_description": raw.get("description") or "",
        "author": owner.get("login") or str(raw.get("full_name") or "").split("/")[0],
        "published_at": raw.get("created_at"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "pushed_at": raw.get("pushed_at"),
        "topics": raw.get("topics") or [],
        "language": raw.get("language"),
        "archived": bool(raw.get("archived")),
        "fork": bool(raw.get("fork")),
        "evidence": {
            "stars": int(raw.get("stargazers_count") or 0),
            "forks": int(raw.get("forks_count") or 0),
            "license": license_data.get("spdx_id"),
            "query": query,
            "source_updated_at": raw.get("updated_at"),
        },
    }


# When the same thing is seen in several sources, the primary record comes from the source with the
# richest first-party metadata; the others are kept as supporting attribution.
SOURCE_PRIORITY = {"GitHub": 0, "Hugging Face": 1, "RSS/Atom Feeds": 2, "Hacker News": 3, "Remotive": 4}


def _strength(item: dict[str, Any]) -> int:
    ev = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    return int(ev.get("stars") or ev.get("likes") or ev.get("points") or 0)


def _norm_title(title: str) -> str:
    title = re.sub(r"^(show|ask|launch) hn:\s*", "", title.lower())
    return re.sub(r"[^a-z0-9 ]+", " ", title).strip()


def _merge(primary: dict[str, Any], other: dict[str, Any], reason: str) -> dict[str, Any]:
    supporting = list(primary.get("supporting_sources") or [])
    for entry in [*(other.get("supporting_sources") or []), {"source": other.get("source"), "source_id": other.get("source_id"), "url": other.get("url"), "match": reason}]:
        if entry["source_id"] != primary.get("source_id") and all(s["source_id"] != entry["source_id"] for s in supporting):
            supporting.append(entry)
    return {**primary, "supporting_sources": supporting}


def deduplicate(items: list[dict[str, Any]], title_similarity: float = 0.92) -> list[dict[str, Any]]:
    # 1. Same record seen by several queries: keep the strongest evidence.
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        key = (item.get("source_id") or item.get("url", "").rstrip("/")).lower()
        previous = by_id.get(key)
        if previous is None or _strength(item) > _strength(previous):
            by_id[key] = item

    # 2. Same canonical URL across sources (e.g. an HN post linking a GitHub repo).
    by_url: dict[str, dict[str, Any]] = {}
    for item in sorted(by_id.values(), key=lambda i: SOURCE_PRIORITY.get(i.get("source", ""), 9)):
        key = item.get("canonical_url") or canonical_url(item.get("url")) or item.get("source_id", "")
        by_url[key] = _merge(by_url[key], item, "canonical_url") if key in by_url else item

    # 3. Near-identical titles from different sources (same announcement, different links).
    # ponytail: O(n^2) over one run's batch (~a few hundred items); bucket by token if batches grow large.
    result: list[dict[str, Any]] = []
    for item in by_url.values():
        title = _norm_title(str(item.get("title", "")))
        for index, kept in enumerate(result):
            if (
                kept.get("source") != item.get("source")
                and item.get("item_type") != "job"
                and len(title) >= 12
                and SequenceMatcher(None, title, _norm_title(str(kept.get("title", "")))).ratio() >= title_similarity
            ):
                result[index] = _merge(kept, item, "title_similarity")
                break
        else:
            result.append(item)
    return result


RELEVANCE_TERMS = {
    "ai",
    "agent",
    "agents",
    "automation",
    "n8n",
    "mcp",
    "llm",
    "local ai",
    "ollama",
    "developer tool",
    "developer tools",
    "computer use",
    "workflow",
    "digital product",
    "saas",
}
# Word boundaries: plain substring matching let "ai" match "maintain", "said", "email", ...
_TERM_PATTERNS = [re.compile(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])") for t in RELEVANCE_TERMS]


def _popularity(item: dict[str, Any]) -> int:
    """Source-native adoption signal. Treated as a signal, not proof of value."""
    ev = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    return int(ev.get("stars") or 0) or int(ev.get("likes") or 0) or int(ev.get("points") or 0)


def select_relevant(
    items: list[dict[str, Any]],
    limit: int = 5,
    store: Any = None,
    include_rejections: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, str]]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    rejections: list[dict[str, str]] = []
    for item in items:
        if item.get("archived") or item.get("fork"):
            rejections.append({"title": str(item.get("title", "")), "reason": "archived or forked repository"})
            continue
        if item.get("item_type") == "job":
            rejections.append({"title": str(item.get("title", "")), "reason": "job listing: indexed without AI analysis"})
            continue
        text = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("raw_description", "")),
                " ".join(str(t) for t in item.get("topics", [])),
            ]
        ).lower().replace("-", " ").replace("_", " ")
        matches = sum(1 for pattern in _TERM_PATTERNS if pattern.search(text))
        if matches == 0:
            rejections.append({"title": str(item.get("title", "")), "reason": "no configured AI or technology focus terms"})
            continue
        stars = _popularity(item)

        # Keyword relevance: primary signal (max 12 pts at 6+ matches)
        keyword_score = min(matches, 6) * 2.0

        # Popularity (stars / likes / points): secondary signal, log-scaled and capped at 500.
        # Weighted by keyword relevance factor so that off-topic items
        # with accidental keyword hits get proportionally less popularity benefit.
        # keyword_factor ranges from 0.17 (1 match) to 1.0 (6+ matches).
        # With S=4.0: a 3-match/20-star item (score≈12.1) beats a 10-match/0-star item (score=12.0)
        # Unrelated items: excluded by 0-keyword gate above, not by popularity cap.
        keyword_factor = min(matches, 6) / 6.0
        star_score = log1p(min(max(stars, 0), 500)) * 4.0 * keyword_factor

        base_score = keyword_score + star_score

        # If a store is passed, deprioritize items already stored that have NO updates
        if store is not None:
            source_id = str(item.get("source_id", ""))
            url = str(item.get("url", ""))
            if store.contains(source_id, url, item.get("canonical_url")):
                has_update, _ = store.has_meaningful_update(source_id, item)
                if not has_update:
                    base_score -= 1000.0  # Push un-updated duplicates below fresh discoveries
                else:
                    base_score += 10.0    # Prioritize items with verified new activity

        scored.append((base_score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    # Fairness within the unchanged analysis budget: the best fresh item of each source gets a slot
    # first, then the remaining slots go by score. With one source this is plain top-N.
    limit = max(0, limit)
    reserved: list[int] = []
    seen_sources: set[str] = set()
    for index, (score, item) in enumerate(scored):
        source = str(item.get("source", ""))
        if score > -500 and source not in seen_sources and len(reserved) < limit:
            seen_sources.add(source)
            reserved.append(index)
    rest = [i for i in range(len(scored)) if i not in set(reserved)]
    chosen = sorted(reserved + rest[: limit - len(reserved)])
    selected = [scored[i][1] for i in chosen]
    if include_rejections:
        return selected, rejections
    return selected
