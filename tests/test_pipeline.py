import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from opportunity_radar.pipeline import run_github_discovery, run_pipeline
from opportunity_radar.store import OpportunityStore


class PipelineTests(unittest.TestCase):
    def test_pipeline_persists_reports_and_skips_duplicates_on_second_run(self):
        raw = [{
            "id": 1,
            "name": "tool",
            "full_name": "acme/tool",
            "html_url": "https://github.com/acme/tool",
            "description": "AI automation tool",
            "created_at": "2026-09-20T00:00:00Z",
            "updated_at": "2026-09-22T00:00:00Z",
            "pushed_at": "2026-09-22T00:00:00Z",
            "stargazers_count": 10,
            "forks_count": 1,
            "language": "Python",
            "topics": ["automation"],
            "license": {"spdx_id": "MIT"},
        }]
        valid_analysis = {
            "category": "useful technology",
            "summary": "A documented AI automation tool.",
            "what_it_does": "The repository description identifies it as an AI automation tool.",
            "why_it_matters": "It matches the stated automation focus.",
            "potential_use_for_us": "Review it before deciding whether to test it.",
            "business_opportunity": "Insufficient evidence of customer demand.",
            "technical_opportunity": "Inspect the Python implementation.",
            "estimated_effort": "small: initial review",
            "recommended_next_action": "Read the repository README.",
            "evidence": ["Description: AI automation tool", "10 stars at discovery"],
            "confidence": "medium",
        }
        with tempfile.TemporaryDirectory() as directory:
            store = OpportunityStore(Path(directory) / "radar.db")
            generate = lambda prompt: json.dumps(valid_analysis)

            first = run_pipeline(raw, "ai automation", store, generate, "2026-09-23T12:00:00+00:00")
            second = run_pipeline(raw, "ai automation", store, generate, "2026-09-23T13:00:00+00:00")

            self.assertEqual(first["stored"], 1)
            self.assertEqual(second["stored"], 0)
            self.assertEqual(second["duplicates"], 1)
            self.assertEqual(len(store.list_reports()), 1)

    def test_pipeline_records_analysis_failure_without_crashing_batch(self):
        raw = [{"id": 2, "full_name": "acme/bad", "html_url": "https://github.com/acme/bad"}]
        with tempfile.TemporaryDirectory() as directory:
            store = OpportunityStore(Path(directory) / "radar.db")

            result = run_pipeline(raw, "ai", store, lambda prompt: "bad", "2026-09-23T12:00:00+00:00")

            self.assertEqual(result["stored"], 0)
            self.assertEqual(result["failed"], 1)
            self.assertIn("valid JSON", result["errors"][0]["error"])
            self.assertEqual(result["analysis_failed"], 1)
            with closing(store._connect()) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_failures").fetchone()[0], 1)

    def test_github_discovery_deduplicates_across_queries_before_analysis(self):
        raw = {
            "id": 3,
            "full_name": "acme/ai-agent",
            "html_url": "https://github.com/acme/ai-agent",
            "description": "AI agent automation toolkit",
            "stargazers_count": 5,
            "forks_count": 1,
            "topics": ["ai-agents"],
        }
        analysis = {
            "category": "technology worth testing",
            "summary": "An AI agent automation toolkit.",
            "what_it_does": "The description identifies an agent automation toolkit.",
            "why_it_matters": "It matches the radar focus.",
            "potential_use_for_us": "Review before testing.",
            "business_opportunity": "Demand is not evidenced.",
            "technical_opportunity": "Inspect its implementation.",
            "estimated_effort": "small: initial review",
            "recommended_next_action": "Read its README.",
            "evidence": ["Description: AI agent automation toolkit"],
            "confidence": "medium",
        }
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            store = OpportunityStore(Path(directory) / "radar.db")

            result = run_github_discovery(
                ["ai agents", "automation"],
                store,
                lambda prompt: json.dumps(analysis),
                lambda query, per_page, token: calls.append(query) or [raw],
                "2026-09-23T12:00:00+00:00",
                max_analyzed=5,
            )

            self.assertEqual(calls, ["ai agents", "automation"])
            self.assertEqual(result["collected"], 2)
            self.assertEqual(result["unique_in_batch"], 1)
            self.assertEqual(result["stored"], 1)


if __name__ == "__main__":
    unittest.main()
