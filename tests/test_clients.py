import unittest
from io import BytesIO
from urllib.error import HTTPError

from opportunity_radar.github import CollectionError, collect_github
from opportunity_radar.ollama import OllamaClient
from opportunity_radar.openrouter import OpenRouterClient, OpenRouterError, _post_json


class ClientTests(unittest.TestCase):
    def test_github_collector_builds_recent_non_fork_search(self):
        captured = {}

        def fake_request(url, headers):
            captured["url"] = url
            captured["headers"] = headers
            return {"items": [{"id": 7}]}

        items = collect_github("ai agents", per_page=5, request_json=fake_request)

        self.assertEqual(items, [{"id": 7}])
        self.assertIn("ai+agents", captured["url"])
        self.assertIn("fork%3Afalse", captured["url"])
        self.assertIn("per_page=5", captured["url"])

    def test_github_collector_rejects_malformed_response(self):
        with self.assertRaises(CollectionError):
            collect_github("ai", request_json=lambda url, headers: {"message": "rate limited"})

    def test_ollama_client_uses_thinking_when_qwen_returns_empty_response(self):
        client = OllamaClient(
            "qwen3.5:9b",
            post_json=lambda url, payload, timeout: {"response": "", "thinking": '{"category":"useful technology"}'},
        )

        response = client.generate("analyze this")

        self.assertEqual(response, '{"category":"useful technology"}')

    def test_ollama_client_returns_generated_text(self):
        captured = {}

        def fake_post(url, payload, timeout):
            captured["url"] = url
            captured["payload"] = payload
            return {"response": '{"category":"useful technology"}'}

        client = OllamaClient("qwen:test", base_url="http://localhost:11434", post_json=fake_post)
        response = client.generate("analyze this")

        self.assertEqual(response, '{"category":"useful technology"}')
        self.assertEqual(captured["payload"]["format"], "json")
        self.assertFalse(captured["payload"]["stream"])

    def test_openrouter_client_uses_configured_model_auth_and_prompt(self):
        captured = {}

        def fake_post(url, payload, headers, timeout):
            captured.update(url=url, payload=payload, headers=headers, timeout=timeout)
            return {"choices": [{"message": {"content": "```json\n{\"category\":\"useful technology\"}\n```"}}]}

        response = OpenRouterClient("nvidia/test:free", "secret-key", 42, fake_post).generate("analyze this")

        self.assertEqual(response, '{"category":"useful technology"}')
        self.assertEqual(captured["url"], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(captured["payload"]["model"], "nvidia/test:free")
        self.assertEqual(captured["payload"]["messages"][0]["content"], "analyze this")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret-key")
        self.assertEqual(captured["timeout"], 42)

    def test_openrouter_client_rejects_missing_or_empty_content(self):
        with self.assertRaisesRegex(OpenRouterError, "OPENROUTER_API_KEY"):
            OpenRouterClient(api_key="")
        client = OpenRouterClient(api_key="secret", post_json=lambda *_: {"choices": [{"message": {"content": ""}}]})
        with self.assertRaisesRegex(OpenRouterError, "empty message content"):
            client.generate("prompt")

    def test_openrouter_client_handles_provider_errors_and_malformed_responses(self):
        client = OpenRouterClient(api_key="secret", post_json=lambda *_: {"error": "bad key secret"})
        with self.assertRaisesRegex(OpenRouterError, r"\[redacted\]"):
            client.generate("prompt")
        malformed = OpenRouterClient(api_key="secret", post_json=lambda *_: {"choices": []})
        with self.assertRaisesRegex(OpenRouterError, "did not contain message content"):
            malformed.generate("prompt")

    def test_openrouter_client_keeps_non_json_message_content_for_diagnostics(self):
        client = OpenRouterClient(
            api_key="secret",
            post_json=lambda *_: {"choices": [{"message": {"content": "I cannot provide that format."}}]},
        )

        self.assertEqual(client.generate("prompt"), "I cannot provide that format.")
        self.assertEqual(client.last_content, "I cannot provide that format.")

    def test_openrouter_http_errors_timeouts_and_malformed_json_are_sanitized(self):
        def http_error(*_args, **_kwargs):
            raise HTTPError("https://example", 401, "unauthorized", None, BytesIO(b'{"error":{"message":"bad secret-key"}}'))

        with self.assertRaisesRegex(OpenRouterError, r"HTTP 401: bad \[redacted\]"):
            _post_json("https://example", {}, {"Authorization": "Bearer secret-key"}, 1, http_error)
        with self.assertRaisesRegex(OpenRouterError, "timed out"):
            _post_json("https://example", {}, {"Authorization": "Bearer secret-key"}, 1, lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))

        class InvalidJsonResponse:
            def __enter__(self): return BytesIO(b"not json")
            def __exit__(self, *_args): return False

        with self.assertRaisesRegex(OpenRouterError, "malformed JSON"):
            _post_json("https://example", {}, {"Authorization": "Bearer secret-key"}, 1, lambda *_args, **_kwargs: InvalidJsonResponse())


if __name__ == "__main__":
    unittest.main()
