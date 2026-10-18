import json
import unittest

from opportunity_radar.n8n_import import build_create_payload


class N8nImportTests(unittest.TestCase):
    def test_create_payload_contains_only_public_api_fields(self):
        workflow = {
            "id": "local-id",
            "name": "Radar",
            "nodes": [],
            "connections": {},
            "settings": {"executionOrder": "v1"},
            "active": False,
            "versionId": "x",
        }

        payload = build_create_payload(workflow)

        self.assertEqual(set(payload), {"name", "nodes", "connections", "settings"})
        self.assertNotIn("id", payload)
        self.assertNotIn("active", payload)


if __name__ == "__main__":
    unittest.main()
