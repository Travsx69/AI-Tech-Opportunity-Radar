"""Builds the configured discovery sources. Each source is a list of independent requests so a
failing query/feed only degrades its own source, and a failing source never stops the others."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from opportunity_radar.core import normalize_github_item
from opportunity_radar.github import collect_github
from opportunity_radar.hackernews import collect_hackernews, normalize_hn_item
from opportunity_radar.sources import collect_feed, collect_huggingface, collect_remotive

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "sources.json"

# Remotive keyword search is loose ("automation" matches office roles), and jobs skip AI analysis,
# so they must pass this gate to be indexed.
# Generic words like "engineer"/"developer" are deliberately absent: they matched service-desk and
# front-end roles in the live check. Title only: Remotive tags are noisy ("AI/ML" on content roles).
JOB_TERMS = re.compile(r"\b(ai|ml|llms?|gpt|genai|machine learning|automations?|n8n|zapier|make\.com|workflows?|integrations?|apis?|agents?|agentic|prompt|devtools|developer tools)\b", re.I)

Request = tuple[str, Callable[[], list[dict[str, Any]]]]


@dataclass
class SourceSpec:
    name: str
    enabled: bool
    access: str = ""
    disabled_reason: str = ""
    min_interval_minutes: int = 0
    requests: list[Request] = field(default_factory=list)
    request_gap_seconds: float = 0.0  # pause between this source's requests (Remotive blocks >2/min)

    def public(self) -> dict[str, Any]:
        """Display-safe description: no URLs with params, no credentials, no paths."""
        return {
            "source_name": self.name,
            "enabled": self.enabled,
            "access": self.access,
            "disabled_reason": self.disabled_reason,
            "min_interval_minutes": self.min_interval_minutes,
            "request_count": len(self.requests),
        }


def load_source_config(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_CONFIG_PATH
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _gate(section: dict[str, Any]) -> tuple[bool, str]:
    """Zero-cost policy: anything needing payment or unavailable credentials stays disabled."""
    if section.get("requires_payment"):
        return False, section.get("disabled_reason") or "Requires payment; disabled by the zero-cost policy."
    if section.get("requires_credentials"):
        return False, section.get("disabled_reason") or "Requires credentials that are not configured."
    if not section.get("enabled", False):
        return False, section.get("disabled_reason") or "Disabled in config/sources.json."
    return True, ""


def _job_relevant(item: dict[str, Any]) -> bool:
    return bool(JOB_TERMS.search(item.get("title", "")))


def build_sources(
    cfg: dict[str, Any],
    discovered_at: str,
    github_queries: list[str],
    per_query: int,
    github_token: str | None = None,
    include_hn: bool = False,
    github_collect: Callable[..., list[dict[str, Any]]] = collect_github,
    hn_collect: Callable[..., list[dict[str, Any]]] = collect_hackernews,
    hf_collect: Callable[..., list[dict[str, Any]]] = collect_huggingface,
    feed_collect: Callable[..., list[dict[str, Any]]] = collect_feed,
    remotive_collect: Callable[..., list[dict[str, Any]]] = collect_remotive,
) -> list[SourceSpec]:
    specs: list[SourceSpec] = []

    gh = cfg.get("github", {"enabled": True})
    enabled, reason = _gate(gh)
    specs.append(SourceSpec("GitHub", enabled, gh.get("access", ""), reason, int(gh.get("min_interval_minutes", 0)), [
        (f"github:{q}", lambda q=q: [normalize_github_item(r, discovered_at, q) for r in github_collect(q, per_query, github_token)])
        for q in github_queries
    ]))

    hn = cfg.get("hacker_news", {"enabled": False})
    enabled, reason = _gate({**hn, "enabled": hn.get("enabled", False) or include_hn})
    hn_queries = hn.get("queries") or [{"query": q} for q in ("Show HN AI", "AI agent", "MCP server", "local LLM", "AI automation")]
    hn_per_query, min_points = int(hn.get("per_query", per_query)), int(hn.get("min_points", 0))
    specs.append(SourceSpec("Hacker News", enabled, hn.get("access", ""), reason, int(hn.get("min_interval_minutes", 0)), [
        (f"hn:{q['query']}", lambda q=q: [
            normalize_hn_item(hit, discovered_at, q["query"], q.get("item_type", "business"))
            for hit in hn_collect(q["query"], hn_per_query, **({"min_points": min_points} if min_points else {}))
        ])
        for q in hn_queries
    ]))

    hf = cfg.get("hugging_face", {})
    enabled, reason = _gate(hf)
    specs.append(SourceSpec("Hugging Face", enabled, hf.get("access", ""), reason, int(hf.get("min_interval_minutes", 0)), [
        (f"hf:{s['kind']}:{s['search']}", lambda s=s: hf_collect(
            s["kind"], s["search"], discovered_at, limit=int(hf.get("limit", 10)), max_pages=int(hf.get("max_pages", 1)),
            min_likes=int(hf.get("min_likes", 0)), max_age_days=hf.get("max_age_days"),
        ))
        for s in hf.get("searches", [])
    ]))

    rss = cfg.get("rss", {})
    enabled, reason = _gate(rss)
    feeds = [f for f in rss.get("feeds", []) if f.get("enabled", True) and not f.get("requires_payment")]
    specs.append(SourceSpec("RSS/Atom Feeds", enabled and bool(feeds), rss.get("access", ""), reason or ("" if feeds else "No feeds enabled."),
                            int(rss.get("min_interval_minutes", 0)), [
        (f"rss:{f['name']}", lambda f=f: feed_collect(f, discovered_at, int(rss.get("max_items_per_feed", 10)), rss.get("max_age_days")))
        for f in feeds
    ]))

    rem = cfg.get("remotive", {})
    enabled, reason = _gate(rem)
    specs.append(SourceSpec("Remotive", enabled, rem.get("access", ""), reason, int(rem.get("min_interval_minutes", 360)), [
        (f"remotive:{s}", lambda s=s: [i for i in remotive_collect(s, discovered_at, int(rem.get("limit", 20))) if _job_relevant(i)])
        for s in rem.get("searches", [])
    ], request_gap_seconds=float(rem.get("request_gap_seconds", 35))))

    ph = cfg.get("product_hunt")
    if ph is not None:
        enabled, reason = _gate(ph)
        # No adapter is implemented: even if someone flips enabled, there is nothing to call.
        specs.append(SourceSpec("Product Hunt", False, ph.get("access", ""), reason or "No adapter implemented.", 0, []))

    for spec in specs:
        if not spec.requests:
            spec.enabled = False
            spec.disabled_reason = spec.disabled_reason or "No queries or feeds configured."
    return specs
