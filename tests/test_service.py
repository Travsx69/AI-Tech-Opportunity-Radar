import json
import threading
import unittest
from urllib.request import Request, urlopen

from opportunity_radar.service import make_server


class ServiceTests(unittest.TestCase):
    def test_health_and_run_endpoints_return_json(self):
        server = make_server("127.0.0.1", 0, object(), runner=lambda config: {"stored": 2, "failed": 0})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(f"{base}/health", timeout=5) as response:
                health = json.load(response)
            request = Request(f"{base}/run", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(health, {"status": "ok"})
        self.assertEqual(result["stored"], 2)


if __name__ == "__main__":
    unittest.main()
