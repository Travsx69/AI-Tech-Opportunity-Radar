from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


# High-signal domains prioritized by the Radar
PRIMARY_TERMS = {
    "agent": 3.0,
    "agents": 3.0,
    "automation": 3.0,
    "workflow": 2.5,
    "mcp": 3.0,
    "n8n": 3.0,
    "llm": 2.5,
    "local ai": 3.0,
    "ollama": 2.5,
    "developer tool": 2.5,
    "developer tools": 2.5,
    "computer use": 3.0,
    "saas": 2.0,
    "micro-saas": 2.5,
    "rag": 2.0,
    "coding agent": 3.0,
    "subagent": 3.0,
    "api": 1.5,
    "cli": 1.5,
    "tooling": 1.5,
    "framework": 1.5,
    "open source": 1.5,
}

PERMISSIVE_LICENSES = {"MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "CC0-1.0", "ISC"}


def calculate_relevance_score(text: str) -> float:
    """Calculate 0-100 topical relevance score based on weighted keyword presence."""
    lowered = text.lower()
    score = 0.0
    for term, weight in PRIMARY_TERMS.items():
        if term in lowered:
            score += weight * 4.0
    return min(100.0, score)


def _extract_evidence_dict(item: dict[str, Any]) -> dict[str, Any]:
    raw_ev = item.get("evidence")
    if isinstance(raw_ev, dict):
        return raw_ev
    extracted: dict[str, Any] = {}
    if isinstance(raw_ev, list):
        for entry in raw_ev:
            if isinstance(entry, str) and ":" in entry:
                k, v = entry.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if "star" in k:
                    try:
                        extracted["stars"] = int("".join(c for c in v if c.isdigit()))
                    except ValueError:
                        pass
                elif "fork" in k:
                    try:
                        extracted["forks"] = int("".join(c for c in v if c.isdigit()))
                    except ValueError:
                        pass
                elif "license" in k:
                    extracted["license"] = v
                elif "point" in k:
                    try:
                        extracted["points"] = int("".join(c for c in v if c.isdigit()))
                    except ValueError:
                        pass
                elif "comment" in k:
                    try:
                        extracted["comments"] = int("".join(c for c in v if c.isdigit()))
                    except ValueError:
                        pass
    return extracted


def calculate_demand_score(item: dict[str, Any]) -> float:
    """Calculate 0-100 demand score using logarithmic scaling of stars, forks, points, comments."""
    evidence = _extract_evidence_dict(item)
    source = str(item.get("source", "")).lower()
    
    if "github" in source or item.get("github_stars") is not None:
        stars = int(item.get("github_stars") or evidence.get("stars") or 0)
        forks = int(evidence.get("forks") or 0)
        star_score = min(80.0, math.log10(max(1, stars)) * 23.75) if stars > 0 else 5.0
        fork_score = min(20.0, math.log10(max(1, forks)) * 8.0) if forks > 0 else 0.0
        return min(100.0, round(star_score + fork_score, 1))
    
    if "hugging face" in source:
        likes = int(evidence.get("likes") or 0)
        downloads = int(evidence.get("downloads") or 0)
        like_score = min(70.0, math.log10(max(1, likes)) * 23.0) if likes > 0 else 5.0
        dl_score = min(30.0, math.log10(max(1, downloads)) * 5.0) if downloads > 0 else 0.0
        return min(100.0, round(like_score + dl_score, 1))

    # Hacker News or discussion post (feeds carry no popularity data and stay at the neutral floor)
    points = int(evidence.get("points") or 0)
    comments = int(evidence.get("comments") or 0)
    pt_score = min(60.0, math.log10(max(1, points)) * 25.0) if points > 0 else 10.0
    cm_score = min(40.0, math.log10(max(1, comments)) * 20.0) if comments > 0 else 5.0
    return min(100.0, round(pt_score + cm_score, 1))


def calculate_recency_score(iso_timestamp: str | None, now: datetime | None = None) -> float:
    """Calculate 0-100 recency score based on days since update/publication."""
    if not iso_timestamp:
        return 50.0
    try:
        ts = iso_timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return 50.0

    current = now or datetime.now(timezone.utc)
    days_old = max(0.0, (current - dt).total_seconds() / 86400.0)

    # Within 2 days = 95-100, 7 days = 85, 30 days = 60, 90 days = 30, >180 days = 10
    if days_old <= 2:
        return 100.0 - (days_old * 2.5)
    elif days_old <= 7:
        return 95.0 - ((days_old - 2) * 2.0)
    elif days_old <= 30:
        return 85.0 - ((days_old - 7) * 1.1)
    elif days_old <= 90:
        return 60.0 - ((days_old - 30) * 0.5)
    else:
        return max(10.0, 30.0 - ((days_old - 90) * 0.1))


def calculate_actionability_score(item: dict[str, Any], ai_report: dict[str, Any] | None = None) -> float:
    """Calculate 0-100 actionability & feasibility score."""
    score = 40.0
    evidence = _extract_evidence_dict(item)
    license_id = str(evidence.get("license") or "").upper()
    
    # Permissive licenses are easier to test, build upon, or integrate
    if any(perm in license_id for perm in PERMISSIVE_LICENSES):
        score += 25.0
    elif license_id:
        score += 10.0  # At least has a declared license
    
    # Description quality & clarity
    desc = str(item.get("raw_description") or "")
    if len(desc) > 30:
        score += 15.0
    
    # AI report recommendations
    if ai_report:
        category = ai_report.get("category", "")
        if category in {"technology worth testing", "useful technology"}:
            score += 10.0
        elif category in {"potential business opportunity", "potential product idea"}:
            score += 15.0
        
        confidence = ai_report.get("confidence", "")
        if confidence == "high":
            score += 10.0
        elif confidence == "medium":
            score += 5.0
            
    return min(100.0, score)


def calculate_evidence_quality_score(item: dict[str, Any]) -> float:
    """Score verifiable evidence in the data packet (0-100)."""
    score = 30.0
    if item.get("url") and str(item["url"]).startswith("http"):
        score += 25.0
    evidence = _extract_evidence_dict(item)
    if evidence.get("stars") is not None or evidence.get("points") is not None or evidence.get("likes") is not None:
        score += 20.0
    if item.get("topics") or evidence.get("comments") is not None:
        score += 15.0
    if item.get("created_at") or item.get("updated_at"):
        score += 10.0
    return min(100.0, score)


def score_opportunity(
    item: dict[str, Any],
    ai_report: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Computes transparent multi-criteria opportunity scoring:
    Returns composite score (0-100) and breakdown components.
    """
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("raw_description", "")),
        " ".join(item.get("topics", [])),
        str(ai_report.get("summary", "") if ai_report else ""),
        str(ai_report.get("what_it_does", "") if ai_report else ""),
    ])

    relevance = calculate_relevance_score(text)
    demand = calculate_demand_score(item)
    
    # Recency checked from pushed_at or updated_at or created_at
    latest_ts = item.get("pushed_at") or item.get("updated_at") or item.get("created_at") or item.get("date_discovered")
    recency = calculate_recency_score(latest_ts, now=now)
    
    actionability = calculate_actionability_score(item, ai_report)
    evidence_quality = calculate_evidence_quality_score(item)

    # Weights:
    # Relevance: 30%, Demand: 25%, Recency: 20%, Actionability: 15%, Evidence Quality: 10%
    composite = (
        relevance * 0.30
        + demand * 0.25
        + recency * 0.20
        + actionability * 0.15
        + evidence_quality * 0.10
    )

    breakdown = {
        "relevance": round(relevance, 1),
        "demand": round(demand, 1),
        "recency": round(recency, 1),
        "actionability": round(actionability, 1),
        "evidence_quality": round(evidence_quality, 1),
    }

    return {
        "score": round(composite, 1),
        "score_breakdown": breakdown,
    }
