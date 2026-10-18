import json
import unittest

from opportunity_radar.analysis import AnalysisError, analyze_item, build_prompt
from opportunity_radar.core import deduplicate, normalize_github_item, select_relevant


class CoreTests(unittest.TestCase):
    def test_normalize_github_item_maps_required_source_fields(self):
        raw = {
            "id": 123,
            "name": "agent-kit",
            "full_name": "acme/agent-kit",
            "html_url": "https://github.com/acme/agent-kit",
            "description": "Build practical AI agents",
            "created_at": "2026-09-20T00:00:00Z",
            "updated_at": "2026-09-22T00:00:00Z",
            "pushed_at": "2026-09-22T00:00:00Z",
            "stargazers_count": 42,
            "forks_count": 5,
            "language": "Python",
            "topics": ["ai-agents", "automation"],
            "license": {"spdx_id": "MIT"},
            "archived": False,
            "fork": False,
        }

        item = normalize_github_item(raw, "2026-09-23T12:00:00+00:00", "ai agents")

        self.assertEqual(item["source_id"], "github:123")
        self.assertEqual(item["title"], "acme/agent-kit")
        self.assertEqual(item["url"], raw["html_url"])
        self.assertEqual(item["date_discovered"], "2026-09-23T12:00:00+00:00")
        self.assertEqual(item["evidence"]["stars"], 42)
        self.assertEqual(item["evidence"]["query"], "ai agents")

    def test_deduplicate_keeps_one_item_per_canonical_url(self):
        first = {"source_id": "github:1", "url": "https://github.com/acme/tool", "evidence": {"stars": 2}}
        stronger_duplicate = {"source_id": "github:1", "url": "https://github.com/acme/tool/", "evidence": {"stars": 8}}

        result = deduplicate([first, stronger_duplicate])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["evidence"]["stars"], 8)

    def test_select_relevant_rejects_unrelated_items_and_limits_results(self):
        relevant = {
            "title": "acme/agent-automation",
            "raw_description": "LLM agent workflow automation for developers",
            "topics": ["ai-agents", "developer-tools"],
            "evidence": {"stars": 20},
            "archived": False,
        }
        unrelated = {
            "title": "acme/css-colors",
            "raw_description": "A palette of web colors",
            "topics": ["css"],
            "evidence": {"stars": 1000},
            "archived": False,
        }

        result = select_relevant([unrelated, relevant], limit=1)

        self.assertEqual(result, [relevant])

    def test_relevance_does_not_reward_zero_star_keyword_stuffing_over_adoption(self):
        keyword_stuffed = {
            "title": "random/repo",
            "raw_description": "AI agent automation n8n MCP LLM local AI computer use workflow SaaS",
            "topics": [],
            "evidence": {"stars": 0},
            "archived": False,
        }
        modest_adoption = {
            "title": "acme/agent-tool",
            "raw_description": "AI agent toolkit",
            "topics": ["ai-agents"],
            "evidence": {"stars": 20},
            "archived": False,
        }

        result = select_relevant([keyword_stuffed, modest_adoption], limit=1)

        self.assertEqual(result, [modest_adoption])

    def test_analysis_prompt_requires_claim_attribution(self):
        prompt = build_prompt({"title": "x", "raw_description": "Production ready", "evidence": {"stars": 0}})

        self.assertIn("repository description claims", prompt)
        self.assertIn("Do not infer", prompt)

    def test_analyze_item_returns_all_required_structured_fields(self):
        item = {
            "title": "acme/agent-kit",
            "source": "GitHub",
            "url": "https://github.com/acme/agent-kit",
            "date_discovered": "2026-09-23T12:00:00+00:00",
            "raw_description": "Build practical AI agents",
            "topics": ["ai-agents"],
            "language": "Python",
            "evidence": {"stars": 42, "forks": 5, "license": "MIT", "query": "ai agents"},
        }
        response = {
            "category": "technology worth testing",
            "summary": "An AI agent development toolkit.",
            "what_it_does": "Provides components for building AI agents.",
            "why_it_matters": "It aligns with AI application development.",
            "potential_use_for_us": "Test it in a small agent prototype.",
            "business_opportunity": "No verified standalone business opportunity yet.",
            "technical_opportunity": "Evaluate its reusable Python components.",
            "estimated_effort": "small: 2-4 hours for a technical spike",
            "recommended_next_action": "Read the README and run its smallest example.",
            "evidence": ["GitHub description says: Build practical AI agents", "42 stars and 5 forks at discovery"],
            "confidence": "medium",
        }

        result = analyze_item(item, lambda prompt: json.dumps(response))

        for field in ("title", "source", "url", "date_discovered", *response.keys()):
            self.assertIn(field, result)
        self.assertEqual(result["category"], "technology worth testing")
        self.assertEqual(result["evidence"], response["evidence"])
        self.assertEqual(result["github_stars"], 42)

    def test_analyze_item_rejects_invalid_ai_json(self):
        item = {"title": "x", "source": "GitHub", "url": "https://example.com", "date_discovered": "now"}

        with self.assertRaises(AnalysisError):
            analyze_item(item, lambda prompt: "not json")

    def test_analyze_item_rejects_openrouter_style_prose_response(self):
        item = {"title": "x", "source": "GitHub", "url": "https://example.com", "date_discovered": "now"}

        with self.assertRaisesRegex(AnalysisError, "not valid JSON"):
            analyze_item(item, lambda prompt: "I cannot provide that format.")


if __name__ == "__main__":
    unittest.main()
