from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from opportunity_radar.analysis import AnalysisError, analyze_item
from opportunity_radar.core import deduplicate, normalize_github_item, select_relevant
from opportunity_radar.hackernews import DEFAULT_HN_QUERIES, collect_hackernews
from opportunity_radar.registry import SourceSpec, build_sources
from opportunity_radar.scoring import score_opportunity
from opportunity_radar.sources import redact
from opportunity_radar.store import OpportunityStore


def run_pipeline(
    raw_items: list[dict[str, Any]],
    query: str,
    store: OpportunityStore,
    generate: Callable[[str], str],
    discovered_at: str,
) -> dict[str, Any]:
    """Runs single-batch normalization, deduplication, scoring, and persistence."""
    normalized = [normalize_github_item(item, discovered_at, query) for item in raw_items]
    unique = deduplicate(normalized)
    result: dict[str, Any] = {
        "collected": len(raw_items),
        "normalized": len(normalized),
        "unique_in_batch": len(unique),
        "duplicates": len(normalized) - len(unique),
        "stored": 0,
        "updated": 0,
        "analysis_failed": 0,
        "failed": 0,
        "reports": [],
        "errors": [],
    }
    for item in unique:
        source_id = item["source_id"]
        url = item["url"]
        is_in_store = store.contains(source_id, url)
        has_update, update_reason = store.has_meaningful_update(source_id, item) if is_in_store else (False, "")
        
        if is_in_store and not has_update:
            result["duplicates"] += 1
            continue
        analysis_started = time.time()
        try:
            report = analyze_item(item, generate)
            scored = score_opportunity(item, report)
            report["score"] = scored["score"]
            report["score_breakdown"] = scored["score_breakdown"]
            if has_update:
                report["update_reason"] = update_reason
            
            store.save_or_update(source_id, report, is_update=is_in_store)
        except (AnalysisError, KeyError, ValueError, RuntimeError) as exc:
            result["failed"] += 1
            result["analysis_failed"] += 1
            result["errors"].append({"title": item.get("title", ""), "error": str(exc), "analysis_seconds": round(time.time() - analysis_started, 2)})
            store.record_analysis_failure(item, str(exc))
            continue

        store.clear_analysis_failure(source_id)

        if is_in_store:
            result["updated"] += 1
        else:
            result["stored"] += 1
        result["reports"].append(report)
    return result


def run_github_discovery(
    queries: list[str],
    store: OpportunityStore,
    generate: Callable[[str], str],
    collect: Callable[[str, int, str | None], list[dict[str, Any]]],
    discovered_at: str,
    max_analyzed: int = 5,
    per_query: int = 5,
    token: str | None = None,
    include_hn: bool = False,
    hn_collector: Callable[[str, int], list[dict[str, Any]]] | None = None,
    hn_queries: list[str] | None = None,
) -> dict[str, Any]:
    """Legacy entry point: GitHub (+ optional HN) only. Delegates to run_discovery."""
    cfg = {"hacker_news": {"enabled": include_hn, "queries": [{"query": q} for q in (hn_queries or DEFAULT_HN_QUERIES)], "per_query": per_query}}
    collector = hn_collector or collect_hackernews
    specs = [
        s for s in build_sources(
            cfg, discovered_at, list(queries), per_query, token,
            github_collect=collect,
            hn_collect=lambda q, n, **kw: collector(q, n, **kw),
        )
        if s.name in {"GitHub", "Hacker News"} and (s.name == "GitHub" or include_hn)
    ]
    return run_discovery(specs, store, generate, discovered_at, max_analyzed=max_analyzed)


def _interval_active(spec: SourceSpec, health: dict[str, Any] | None, now: datetime) -> bool:
    """Conservative polling: skip a source whose last successful collection is newer than its interval."""
    if not spec.min_interval_minutes or not health or not health.get("last_success_at"):
        return False
    try:
        last = datetime.fromisoformat(health["last_success_at"])
    except ValueError:
        return False
    return now - last < timedelta(minutes=spec.min_interval_minutes)


def run_discovery(
    sources: list[SourceSpec],
    store: OpportunityStore,
    generate: Callable[[str], str],
    discovered_at: str,
    max_analyzed: int = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """
    Orchestrates discovery across sources with deduplication,
    starvation prevention, evidence scoring, and persistent observability.
    Each source and each of its requests is isolated: failures degrade only that source.
    AI analysis is capped at max_analyzed per run regardless of how many sources are enabled.
    """
    start_time = time.time()
    now = datetime.now(timezone.utc)
    started_iso = now.isoformat()
    run_id = f"run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    normalized: list[dict[str, Any]] = []
    collection_errors: list[dict[str, str]] = []
    source_stats: dict[str, dict[str, Any]] = {}
    health = {h["source_name"]: h for h in store.get_source_health()}

    # 1. Collect from every enabled source
    for spec in sources:
        if not spec.enabled:
            source_stats[spec.name] = {"collected": 0, "status": "disabled", "error": "", "reason": spec.disabled_reason}
            continue
        if _interval_active(spec, health.get(spec.name), now):
            source_stats[spec.name] = {"collected": 0, "status": "skipped", "error": "",
                                       "reason": f"polled less than {spec.min_interval_minutes} min ago"}
            continue
        source_started = time.time()
        collected: list[dict[str, Any]] = []
        ok = failed = 0
        last_error = ""
        for index, (label, request) in enumerate(spec.requests):
            if index and spec.request_gap_seconds:
                sleep(spec.request_gap_seconds)
            try:
                collected.extend(request())
                ok += 1
            except Exception as exc:  # isolate every request: one bad feed/query never stops the run
                last_error = redact(exc)
                collection_errors.append({"query": label, "error": last_error})
                failed += 1
        status = "ok" if failed == 0 else ("degraded" if ok else "failed")
        duration = round(time.time() - source_started, 2)
        source_stats[spec.name] = {"collected": len(collected), "status": status, "error": last_error,
                                   "requests_ok": ok, "requests_failed": failed, "duration_seconds": duration}
        store.update_source_health(spec.name, status, len(collected), last_error, duration, ok, failed)
        normalized.extend(collected)

    # In-batch deduplication (source id, canonical URL, then near-identical titles across sources)
    unique = deduplicate(normalized)

    # Index every record with first/last-seen; the merged primary carries its supporting sources.
    index_records = {item["source_id"]: item for item in normalized}
    index_records.update({item["source_id"]: item for item in unique})
    indexed = store.upsert_discovered(list(index_records.values()), discovered_at)
    # Records that match an existing opportunity refresh its last_seen and attribution (score untouched).
    store.touch_opportunities(unique, discovered_at)

    # Prioritize candidates: new items or meaningfully updated items first to prevent starvation!
    relevant, rejections = select_relevant(unique, max_analyzed, store=store, include_rejections=True)

    result: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_iso,
        "stopped_at": "",
        "duration_seconds": 0.0,
        "collected": len(normalized),
        "normalized": len(normalized),
        "unique_in_batch": len(unique),
        "relevant_selected": len(relevant),
        "duplicates": len(normalized) - len(unique),
        "stored": 0,
        "updated": 0,
        "rejected": len(rejections),
        "analysis_failed": 0,
        "collection_failed": len(collection_errors),
        "failed": len(collection_errors),
        "indexed_new": indexed["new"],
        "indexed_seen_again": indexed["seen_again"],
        "reports": [],
        "errors": collection_errors,
        "rejections": rejections[:50],  # bounded: the run summary is stored and synced
        "sources": source_stats,
    }

    for item in relevant:
        source_id = item["source_id"]
        url = item["url"]
        is_in_store = store.contains(source_id, url)
        has_update, update_reason = store.has_meaningful_update(source_id, item) if is_in_store else (False, "")

        if is_in_store and not has_update:
            result["duplicates"] += 1
            continue

        analysis_started = time.time()
        try:
            report = analyze_item(item, generate)
            scored = score_opportunity(item, report)
            report["score"] = scored["score"]
            report["score_breakdown"] = scored["score_breakdown"]
            if has_update:
                report["update_reason"] = update_reason

            store.save_or_update(source_id, report, is_update=is_in_store)
        except (AnalysisError, KeyError, ValueError, RuntimeError) as exc:
            result["failed"] += 1
            result["analysis_failed"] += 1
            error = {"title": item.get("title", ""), "error": redact(exc), "analysis_seconds": round(time.time() - analysis_started, 2)}
            result["errors"].append(error)
            store.record_analysis_failure(item, redact(exc))
            continue

        store.clear_analysis_failure(source_id)

        if is_in_store:
            result["updated"] += 1
        else:
            result["stored"] += 1
        report["analysis_seconds"] = round(time.time() - analysis_started, 2)
        result["reports"].append(report)

    stopped_iso = datetime.now(timezone.utc).isoformat()
    duration = round(time.time() - start_time, 2)
    result["stopped_at"] = stopped_iso
    result["duration_seconds"] = duration
    attempted = [s for s in source_stats.values() if s["status"] in {"ok", "degraded", "failed"}]
    if attempted and all(s["status"] == "failed" for s in attempted):
        result["status"] = "failed"  # nothing could be collected from any source
    else:
        result["status"] = "success" if result["failed"] == 0 else "partial_failure"

    # Persist run summary for observability
    store.record_run(result)

    return result
