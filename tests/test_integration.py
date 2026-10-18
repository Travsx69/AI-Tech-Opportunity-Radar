"""
Additional tests for Phase G:
- API endpoints (opportunities, runs, sources)
- HackerNews collection and normalization
- Scoring functions
- Second-run duplicate handling via run_github_discovery
"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from opportunity_radar.hackernews import collect_hackernews, normalize_hn_item, HackerNewsError
from opportunity_radar.scoring import (
    calculate_relevance_score,
    calculate_demand_score,
    calculate_recency_score,
    calculate_actionability_score,
    score_opportunity,
)
from opportunity_radar.store import OpportunityStore
from opportunity_radar.pipeline import run_github_discovery
from opportunity_radar.service import make_server


SAMPLE_ANALYSIS = {
    "category": "technology worth testing",
    "summary": "An MCP agent framework.",
    "what_it_does": "The repository description claims it builds MCP agents.",
    "why_it_matters": "MCP tooling is in high demand.",
    "potential_use_for_us": "Evaluate for a small integration test.",
    "business_opportunity": "Insufficient demand evidence.",
    "technical_opportunity": "Inspect the Python library.",
    "estimated_effort": "small: initial review",
    "recommended_next_action": "Read the README.",
    "evidence": ["Description: MCP agent framework", "12 stars at discovery"],
    "confidence": "medium",
}

SAMPLE_GITHUB_RAW = {
    "id": 42,
    "full_name": "acme/mcp-framework",
    "html_url": "https://github.com/acme/mcp-framework",
    "description": "MCP agent automation framework",
    "stargazers_count": 12,
    "forks_count": 2,
    "topics": ["mcp", "agents"],
    "license": {"spdx_id": "MIT"},
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": "2026-10-01T00:00:00Z",
    "pushed_at": "2026-10-01T00:00:00Z",
    "language": "Python",
    "archived": False,
    "fork": False,
}


class DashboardAPITests(unittest.TestCase):
    """Tests for HTTP service API endpoints using a real temporary store."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = OpportunityStore(Path(self.tmpdir.name) / "radar.db")

        # Pre-populate the store with one opportunity
        from opportunity_radar.app import RadarConfig, run_once

        config = RadarConfig(
            data_dir=Path(self.tmpdir.name),
            queries=("mcp agent",),
            max_analyzed=5,
            per_query=5,
        )
        run_once(
            config,
            generate=lambda prompt: json.dumps(SAMPLE_ANALYSIS),
            collect=lambda query, per_page, token: [SAMPLE_GITHUB_RAW],
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def _start_server(self):
        from opportunity_radar.app import RadarConfig

        config = RadarConfig(data_dir=Path(self.tmpdir.name))
        server = make_server("127.0.0.1", 0, config, runner=lambda c: {"stored": 0, "failed": 0})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_health_returns_exact_json(self):
        server, thread = self._start_server()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/health", timeout=5) as r:
                data = json.load(r)
            self.assertEqual(data, {"status": "ok"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_opportunities_api_returns_stored_records(self):
        server, thread = self._start_server()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/opportunities", timeout=5) as r:
                data = json.load(r)
            self.assertIn("opportunities", data)
            self.assertGreaterEqual(data["count"], 1)
            titles = [o["title"] for o in data["opportunities"]]
            self.assertIn("acme/mcp-framework", titles)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_runs_api_returns_run_history(self):
        server, thread = self._start_server()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/runs", timeout=5) as r:
                data = json.load(r)
            self.assertIn("runs", data)
            # run_once triggers run_github_discovery which calls record_run
            self.assertGreaterEqual(data["count"], 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_sources_api_returns_health_records(self):
        server, thread = self._start_server()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/sources", timeout=5) as r:
                data = json.load(r)
            self.assertIn("sources", data)
            # After a discovery run, GitHub source health should be recorded
            source_names = [s["source_name"] for s in data["sources"]]
            self.assertIn("GitHub", source_names)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_dashboard_html_loads(self):
        server, thread = self._start_server()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5) as r:
                html = r.read().decode("utf-8")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("Opportunity Radar", html)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_unknown_route_returns_404(self):
        from urllib.error import HTTPError

        server, thread = self._start_server()
        try:
            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"http://127.0.0.1:{server.server_port}/nonexistent", timeout=5)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class HackerNewsTests(unittest.TestCase):
    """Tests for HackerNews adapter."""

    def test_collect_hackernews_returns_hits(self):
        fake_hit = {
            "objectID": "12345",
            "title": "Show HN: AI automation agent",
            "url": "https://example.com/project",
            "story_text": "",
            "points": 42,
            "num_comments": 15,
            "author": "testuser",
            "created_at": "2026-10-01T10:00:00.000Z",
        }
        hits = collect_hackernews(
            "AI agent",
            per_page=5,
            request_json=lambda url, headers: {"hits": [fake_hit]},
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["objectID"], "12345")

    def test_collect_hackernews_raises_on_malformed_response(self):
        with self.assertRaises(HackerNewsError):
            collect_hackernews(
                "AI",
                request_json=lambda url, headers: {"error": "bad"},
            )

    def test_normalize_hn_item_produces_correct_schema(self):
        hit = {
            "objectID": "99",
            "title": "AI automation tool",
            "url": "https://example.com/tool",
            "story_text": "A great AI tool for automation",
            "points": 55,
            "num_comments": 10,
            "author": "dev",
            "created_at": "2026-10-01T10:00:00.000Z",
        }
        item = normalize_hn_item(hit, "2026-10-11T00:00:00+00:00", "AI automation")
        self.assertEqual(item["source_id"], "hn:99")
        self.assertEqual(item["source"], "Hacker News")
        self.assertEqual(item["title"], "AI automation tool")
        self.assertFalse(item["archived"])
        self.assertFalse(item["fork"])
        self.assertEqual(item["evidence"]["points"], 55)
        self.assertEqual(item["evidence"]["comments"], 10)
        self.assertIn("hacker-news", item["topics"])

    def test_hn_item_uses_discussion_url_when_no_external_url(self):
        hit = {
            "objectID": "77",
            "title": "Ask HN: AI tools",
            "url": None,
            "story_text": "What AI tools do you use?",
            "points": 10,
            "num_comments": 5,
            "author": "q",
            "created_at": "2026-10-01T00:00:00.000Z",
        }
        item = normalize_hn_item(hit, "2026-10-11T00:00:00+00:00", "AI tools")
        self.assertEqual(item["url"], "https://news.ycombinator.com/item?id=77")


class ScoringTests(unittest.TestCase):
    """Tests for scoring module functions."""

    def test_relevance_score_is_zero_for_unrelated_text(self):
        score = calculate_relevance_score("CSS animations and web colors")
        self.assertEqual(score, 0.0)

    def test_relevance_score_high_for_ai_agent_mcp(self):
        score = calculate_relevance_score("AI agent automation MCP server workflow")
        self.assertGreater(score, 40.0)

    def test_demand_score_uses_stars_for_github(self):
        item_github = {"source": "GitHub", "evidence": {"stars": 100, "forks": 10}}
        item_no_stars = {"source": "GitHub", "evidence": {"stars": 0}}
        score_with_stars = calculate_demand_score(item_github)
        score_no_stars = calculate_demand_score(item_no_stars)
        self.assertGreater(score_with_stars, score_no_stars)

    def test_demand_score_uses_points_for_hackernews(self):
        item_hn = {"source": "Hacker News", "evidence": {"points": 50, "comments": 20}}
        score = calculate_demand_score(item_hn)
        self.assertGreater(score, 10.0)

    def test_recency_score_is_high_for_recent_timestamp(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        score = calculate_recency_score(recent)
        self.assertGreater(score, 90.0)

    def test_recency_score_is_low_for_old_timestamp(self):
        score = calculate_recency_score("2025-01-01T00:00:00Z")
        self.assertLess(score, 20.0)

    def test_recency_score_defaults_for_missing_timestamp(self):
        score = calculate_recency_score(None)
        self.assertEqual(score, 50.0)

    def test_score_opportunity_returns_composite_and_breakdown(self):
        item = {
            "title": "acme/ai-agent",
            "raw_description": "AI agent automation workflow",
            "source": "GitHub",
            "evidence": {"stars": 50, "forks": 5},
            "topics": ["ai-agents"],
            "pushed_at": "2026-10-10T00:00:00Z",
        }
        result = score_opportunity(item)
        self.assertIn("score", result)
        self.assertIn("score_breakdown", result)
        bd = result["score_breakdown"]
        for key in ("relevance", "demand", "recency", "actionability", "evidence_quality"):
            self.assertIn(key, bd)
        self.assertGreater(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class SecondRunDuplicateTests(unittest.TestCase):
    """Tests that a second run does not create duplicate records or silently discard updates."""

    def test_second_run_skips_exact_duplicate(self):
        raw = [SAMPLE_GITHUB_RAW]

        with tempfile.TemporaryDirectory() as directory:
            store = OpportunityStore(Path(directory) / "radar.db")
            generate = lambda prompt: json.dumps(SAMPLE_ANALYSIS)
            collect = lambda query, per_page, token: raw

            first = run_github_discovery(
                ["mcp agent"], store, generate, collect,
                "2026-10-01T00:00:00+00:00", max_analyzed=5,
            )
            second = run_github_discovery(
                ["mcp agent"], store, generate, collect,
                "2026-10-01T01:00:00+00:00", max_analyzed=5,
            )

            self.assertEqual(first["stored"], 1)
            self.assertEqual(second["stored"], 0)
            # Should NOT re-store the unchanged item
            self.assertEqual(len(store.list_reports()), 1)

    def test_second_run_records_meaningful_star_update(self):
        raw_v1 = dict(SAMPLE_GITHUB_RAW, stargazers_count=12)
        raw_v2 = dict(SAMPLE_GITHUB_RAW, stargazers_count=150)  # >10% jump

        with tempfile.TemporaryDirectory() as directory:
            store = OpportunityStore(Path(directory) / "radar.db")
            generate = lambda prompt: json.dumps(SAMPLE_ANALYSIS)

            run_github_discovery(
                ["mcp agent"], store, generate,
                lambda q, pp, tok: [raw_v1],
                "2026-10-01T00:00:00+00:00", max_analyzed=5,
            )
            second = run_github_discovery(
                ["mcp agent"], store, generate,
                lambda q, pp, tok: [raw_v2],
                "2026-10-02T00:00:00+00:00", max_analyzed=5,
            )

            # Should update the existing record (not add a duplicate)
            self.assertEqual(second["updated"], 1)
            self.assertEqual(len(store.list_reports()), 1)


if __name__ == "__main__":
    unittest.main()
