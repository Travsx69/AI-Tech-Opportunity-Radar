from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from opportunity_radar.github import collect_github
from opportunity_radar.ollama import OllamaClient
from opportunity_radar.openrouter import OpenRouterClient
from opportunity_radar.pipeline import run_discovery, run_github_discovery
from opportunity_radar.registry import DEFAULT_CONFIG_PATH, SourceSpec, build_sources, load_source_config
from opportunity_radar.store import OpportunityStore


DEFAULT_QUERIES = (
    "AI agent automation",
    "n8n MCP local LLM",
    "LLM application developer tool",
    "computer use AI",
    "coding agent loop",
    "MCP server",
)


@dataclass(frozen=True)
class RadarConfig:
    data_dir: Path = Path("data")
    queries: tuple[str, ...] = DEFAULT_QUERIES
    max_analyzed: int = 5
    per_query: int = 8
    ollama_model: str = "qwen3.5:9b"
    ollama_url: str = "http://localhost:11434"
    ai_provider: str = "ollama"
    openrouter_model: str = "openrouter/free"
    openrouter_api_key: str | None = None
    openrouter_timeout: int = 120
    github_token: str | None = None
    include_hn: bool = False
    # None = legacy GitHub(+HN) only. from_env() points this at config/sources.json.
    sources_config: Path | None = None

    @classmethod
    def from_env(cls, data_dir: Path | None = None) -> "RadarConfig":
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        include_hn = os.getenv("RADAR_INCLUDE_HN", "false").lower() in {"1", "true", "yes"}
        sources_config = os.getenv("RADAR_SOURCES_CONFIG")
        return cls(
            sources_config=Path(sources_config) if sources_config else DEFAULT_CONFIG_PATH,
            data_dir=data_dir or Path(os.getenv("RADAR_DATA_DIR", "data")),
            max_analyzed=int(os.getenv("RADAR_MAX_ANALYZED", "5")),
            per_query=int(os.getenv("RADAR_PER_QUERY", "8")),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ai_provider=os.getenv("AI_PROVIDER", "ollama").strip().lower(),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            openrouter_timeout=max(1, min(int(os.getenv("OPENROUTER_TIMEOUT", "120")), 300)),
            github_token=token.strip() if token else None,
            include_hn=include_hn,
        )


def configured_sources(
    config: RadarConfig,
    discovered_at: str | None = None,
    collect: Callable | None = None,
    hn_collector: Callable | None = None,
) -> list[SourceSpec]:
    """Source specs for this config. Requests are lazy; building the list makes no network calls."""
    if config.sources_config is None:
        cfg = {"hacker_news": {"enabled": config.include_hn}}
        names = {"GitHub", "Hacker News"}
    else:
        cfg, names = load_source_config(config.sources_config), None
    kwargs: dict = {"github_collect": collect} if collect else {}
    if hn_collector:
        kwargs["hn_collect"] = hn_collector
    specs = build_sources(
        cfg, discovered_at or datetime.now(timezone.utc).isoformat(), list(config.queries), config.per_query,
        config.github_token, config.include_hn, **kwargs,
    )
    return [s for s in specs if names is None or s.name in names]


def run_once(
    config: RadarConfig,
    generate: Callable[[str], str] | None = None,
    collect: Callable | None = None,
    hn_collector: Callable | None = None,
) -> dict:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    store = OpportunityStore(config.data_dir / "radar.db")
    if generate:
        generator = generate
    elif config.ai_provider == "ollama":
        generator = OllamaClient(config.ollama_model, config.ollama_url, think=False).generate
    elif config.ai_provider == "openrouter":
        generator = OpenRouterClient(
            config.openrouter_model, config.openrouter_api_key, config.openrouter_timeout
        ).generate
    else:
        raise ValueError("AI_PROVIDER must be 'ollama' or 'openrouter'")
    collector = collect or collect_github
    discovered_at = datetime.now(timezone.utc).isoformat()
    if config.sources_config is not None:
        result = run_discovery(
            configured_sources(config, discovered_at, collect=collector, hn_collector=hn_collector),
            store,
            generator,
            discovered_at,
            max_analyzed=config.max_analyzed,
        )
    else:
        result = run_github_discovery(
            list(config.queries),
            store,
            generator,
            collector,
            discovered_at,
            max_analyzed=config.max_analyzed,
            per_query=config.per_query,
            token=config.github_token,
            include_hn=config.include_hn,
            hn_collector=hn_collector,
        )
    export_path = config.data_dir / "opportunities.json"
    temporary = export_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(store.list_reports(), indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(export_path)
    return result



def main() -> int:
    parser = argparse.ArgumentParser(description="Discover and analyze practical GitHub AI opportunities.")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--max-analyzed", type=int, default=None)
    args = parser.parse_args()
    config = RadarConfig.from_env(args.data_dir)
    if args.max_analyzed is not None:
        config = RadarConfig(**{**config.__dict__, "max_analyzed": args.max_analyzed})
    result = run_once(config)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
