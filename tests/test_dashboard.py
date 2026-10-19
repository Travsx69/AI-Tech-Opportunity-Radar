import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from opportunity_radar.dashboard import DASHBOARD_HTML


class DashboardTests(unittest.TestCase):
    def script(self) -> str:
        return DASHBOARD_HTML.rsplit("<script>", 1)[1].split("</script>", 1)[0]

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_inline_script_is_valid_javascript(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "dashboard.js"
            path.write_text(self.script(), encoding="utf-8")
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_reads_live_endpoints_and_keeps_existing_views(self):
        for endpoint in ("/api/opportunities", "/api/items", "/api/runs", "/api/sources", '"/run"'):
            self.assertIn(endpoint, self.script())
        for view in ('data-tab="feed"', 'data-tab="items"', 'data-tab="runs"', 'data-tab="sources"', 'id="drawer"',
                     'id="categoryFilter"', 'id="sourceFilter"', 'id="typeFilter"', 'id="scoreFilter"', 'id="sortFilter"'):
            self.assertIn(view, DASHBOARD_HTML)

    def test_untrusted_text_is_not_injected_as_html(self):
        script = self.script()
        self.assertNotIn("innerHTML", script)
        self.assertIn("safeHref", script)  # links only accept http(s)


if __name__ == "__main__":
    unittest.main()
