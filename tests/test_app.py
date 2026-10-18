import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opportunity_radar.app import RadarConfig, run_once


class AppTests(unittest.TestCase):
    def test_provider_defaults_to_ollama_and_selects_openrouter_only_when_requested(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(RadarConfig.from_env().ai_provider, "ollama")
        with tempfile.TemporaryDirectory() as directory, patch("opportunity_radar.app.OllamaClient") as ollama:
            run_once(RadarConfig(data_dir=Path(directory), queries=(), max_analyzed=0), collect=lambda *_: [])
        ollama.assert_called_once_with("qwen3.5:9b", "http://localhost:11434", think=False)
        with patch.dict("os.environ", {"AI_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "test-key"}, clear=True):
            config = RadarConfig.from_env()
        with tempfile.TemporaryDirectory() as directory, patch("opportunity_radar.app.OpenRouterClient") as openrouter, patch("opportunity_radar.app.OllamaClient") as ollama:
            run_once(RadarConfig(**{**config.__dict__, "data_dir": Path(directory), "queries": (), "max_analyzed": 0, "sources_config": None}), collect=lambda *_: [])
        openrouter.assert_called_once_with("openrouter/free", "test-key", 120)
        ollama.assert_not_called()

    def test_openrouter_missing_key_is_a_clear_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            config = RadarConfig(data_dir=Path(directory), queries=(), ai_provider="openrouter")
            with self.assertRaisesRegex(Exception, "OPENROUTER_API_KEY"):
                run_once(config, collect=lambda *_: [])

    def test_run_once_writes_current_report_export(self):
        raw = {
            "id": 9,
            "full_name": "acme/mcp-agent",
            "html_url": "https://github.com/acme/mcp-agent",
            "description": "MCP agent developer tool",
            "stargazers_count": 12,
            "forks_count": 2,
            "topics": ["mcp", "agents"],
        }
        analysis = {
            "category": "useful technology",
            "summary": "An MCP agent developer tool.",
            "what_it_does": "The description identifies an MCP agent tool.",
            "why_it_matters": "It matches the radar's technical focus.",
            "potential_use_for_us": "Review the repository.",
            "business_opportunity": "No demand evidence is available.",
            "technical_opportunity": "Inspect its MCP implementation.",
            "estimated_effort": "small: initial review",
            "recommended_next_action": "Read its README.",
            "evidence": ["Description: MCP agent developer tool"],
            "confidence": "medium",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = RadarConfig(data_dir=root, queries=("mcp agent",), max_analyzed=3, per_query=2)

            result = run_once(
                config,
                generate=lambda prompt: json.dumps(analysis),
                collect=lambda query, per_page, token: [raw],
            )

            exported = json.loads((root / "opportunities.json").read_text(encoding="utf-8"))
            self.assertEqual(result["stored"], 1)
            self.assertEqual(len(exported), 1)
            self.assertEqual(exported[0]["title"], "acme/mcp-agent")


if __name__ == "__main__":
    unittest.main()
