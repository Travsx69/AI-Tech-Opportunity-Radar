from __future__ import annotations

import json
from typing import Any, Callable


class AnalysisError(ValueError):
    """Raised when an AI response cannot be trusted as structured output."""


ANALYSIS_FIELDS = (
    "category",
    "summary",
    "what_it_does",
    "why_it_matters",
    "potential_use_for_us",
    "business_opportunity",
    "technical_opportunity",
    "estimated_effort",
    "recommended_next_action",
    "evidence",
    "confidence",
)
CATEGORIES = {
    "interesting technology",
    "useful technology",
    "technology worth testing",
    "potential product idea",
    "potential business opportunity",
}
CONFIDENCE_LEVELS = {"low", "medium", "high"}


def build_prompt(item: dict[str, Any]) -> str:
    evidence_packet = {
        "title": item.get("title"),
        "source": item.get("source"),
        "url": item.get("url"),
        "description": item.get("raw_description", ""),
        "topics": item.get("topics", []),
        "language": item.get("language"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "pushed_at": item.get("pushed_at"),
        "repository_metrics": item.get("evidence", {}),
        "item_type": item.get("item_type"),
        "author": item.get("author"),
        "also_seen_in": [s.get("source") for s in item.get("supporting_sources") or []],
    }
    schema = {
        "category": "one exact allowed category",
        "summary": "string",
        "what_it_does": "string",
        "why_it_matters": "string",
        "potential_use_for_us": "string",
        "business_opportunity": "string",
        "technical_opportunity": "string",
        "estimated_effort": "string",
        "recommended_next_action": "string",
        "evidence": ["specific fact from the evidence packet"],
        "confidence": "low|medium|high",
    }
    return (
        "You are a skeptical opportunity analyst. Analyze only the supplied evidence packet. "
        "Treat description and topics as publisher claims, not independently verified facts. "
        "When using description details, write 'the repository description claims' or equivalent attribution "
        "(for news, feeds, or discussions: 'the publisher states' or 'the post claims'). "
        "Popularity metrics (stars, likes, points, downloads) are signals, not proof of demand or value. "
        "Do not infer documentation quality, production readiness, adoption, demand, revenue, capabilities, "
        "implementation completeness, or required effort beyond the packet. "
        "Never invent customer demand or implementation details. "
        "If evidence is insufficient, say so explicitly and lower confidence. "
        "Classify with exactly one of: " + ", ".join(sorted(CATEGORIES)) + ". "
        "Return one JSON object only, with no markdown, following this schema: "
        + json.dumps(schema)
        + "\nEvidence packet:\n"
        + json.dumps(evidence_packet, ensure_ascii=False)
    )


def analyze_item(item: dict[str, Any], generate: Callable[[str], str]) -> dict[str, Any]:
    raw_response = generate(build_prompt(item))
    try:
        analysis = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AnalysisError("AI response was not valid JSON") from exc
    if not isinstance(analysis, dict):
        raise AnalysisError("AI response must be a JSON object")
    missing = [field for field in ANALYSIS_FIELDS if field not in analysis]
    if missing:
        raise AnalysisError(f"AI response missing fields: {', '.join(missing)}")
    if analysis["category"] not in CATEGORIES:
        raise AnalysisError("AI response used an unsupported category")
    if analysis["confidence"] not in CONFIDENCE_LEVELS:
        raise AnalysisError("AI response used an unsupported confidence")
    if not isinstance(analysis["evidence"], list) or not analysis["evidence"]:
        raise AnalysisError("AI response evidence must be a non-empty list")
    for field in ANALYSIS_FIELDS:
        if field != "evidence" and not isinstance(analysis[field], str):
            raise AnalysisError(f"AI response field {field} must be a string")
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    is_github = item.get("source", "GitHub") == "GitHub"
    report = {
        "title": item.get("title", ""),
        "source": item.get("source", ""),
        "url": item.get("url", ""),
        "date_discovered": item.get("date_discovered", ""),
        # Stars only exist for GitHub; other sources get None rather than an invented 0.
        "github_stars": int(evidence.get("stars", 0)) if is_github else None,
        **analysis,
    }
    if item.get("item_type"):
        report["item_type"] = item["item_type"]
    if item.get("source_id"):
        report["source_id"] = item["source_id"]
    if item.get("supporting_sources"):
        report["supporting_sources"] = item["supporting_sources"]
    return report
