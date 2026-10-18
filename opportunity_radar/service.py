from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse

from opportunity_radar.app import RadarConfig, configured_sources, run_once
from opportunity_radar.dashboard import DASHBOARD_HTML
from opportunity_radar.sources import redact
from opportunity_radar.store import OpportunityStore


def source_report(config: object, store: OpportunityStore | None) -> list[dict]:
    """Configured sources joined with persisted health. Keeps the original five health fields
    (the website connector syncs those) and adds enabled/healthy/collecting flags. No secrets or paths."""
    health = {h["source_name"]: h for h in (store.get_source_health() if store else [])}
    specs = configured_sources(config) if isinstance(config, RadarConfig) else []
    rows = []
    for spec in specs:
        h = health.pop(spec.name, {})
        status = h.get("last_status") or ("never_run" if spec.enabled else "disabled")
        rows.append({
            "source_name": spec.name,
            "last_run_at": h.get("last_run_at"),
            "last_status": status,
            "items_collected": h.get("items_collected", 0),
            "last_error": redact(h.get("last_error", "")),
            "configured": True,
            "enabled": spec.enabled,
            "disabled_reason": spec.disabled_reason,
            "access": spec.access,
            "min_interval_minutes": spec.min_interval_minutes,
            "request_count": len(spec.requests),
            "last_success_at": h.get("last_success_at") or None,
            "last_duration_seconds": h.get("last_duration_seconds"),
            "requests_ok": h.get("requests_ok", 0),
            "requests_failed": h.get("requests_failed", 0),
            "indexed_items": h.get("indexed_items", 0),
            "opportunities": h.get("opportunities", 0),
            "healthy": spec.enabled and status == "ok",
            "collecting": spec.enabled and status in {"ok", "degraded"} and h.get("items_collected", 0) > 0,
        })
    for name, h in health.items():  # history for a source no longer in the config
        rows.append({**h, "last_error": redact(h.get("last_error", "")), "configured": False, "enabled": False,
                     "healthy": False, "collecting": False, "last_success_at": h.get("last_success_at") or None})
    return rows


def summarize_sources(rows: list[dict]) -> dict:
    return {
        "configured": sum(1 for r in rows if r.get("configured")),
        "enabled": sum(1 for r in rows if r.get("enabled")),
        "healthy": sum(1 for r in rows if r.get("healthy")),
        "collecting": sum(1 for r in rows if r.get("collecting")),
    }


def make_server(host: str, port: int, config: RadarConfig, runner: Callable = run_once) -> ThreadingHTTPServer:
    run_lock = threading.Lock()
    # Lazy or explicit store reference
    data_dir = getattr(config, "data_dir", None)
    store = OpportunityStore(data_dir / "radar.db") if data_dir else None

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict | list) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, status: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            # 1. Web Dashboard UI
            if path in {"/", "/dashboard"}:
                self._send_html(200, DASHBOARD_HTML)
                return

            # 2. Health check (compatible with n8n and monitoring)
            if path == "/health":
                self._send(200, {"status": "ok"})
                return

            param = lambda name, default=None: params.get(name, [default])[0]  # noqa: E731
            try:
                limit = int(param("limit", 100))
                offset = int(param("offset", 0))
                score_str = param("min_score")
                min_score = float(score_str) if score_str else None
            except ValueError:
                self._send(400, {"error": "limit, offset and min_score must be numbers"})
                return

            # 3. Opportunities API
            if path == "/api/opportunities":
                if not store:
                    self._send(200, {"opportunities": []})
                    return
                opps = store.list_opportunities(
                    category=param("category"),
                    source=param("source"),
                    min_score=min_score,
                    search=param("search"),
                    sort_by=param("sort", "score"),
                    limit=limit,
                    offset=offset,
                    item_type=param("type"),
                )
                self._send(200, {"opportunities": opps, "count": len(opps)})
                return

            # 3b. Every indexed record across sources, including jobs (not AI-analyzed)
            if path == "/api/items":
                items = store.list_items(param("type"), param("source"), param("search"), limit, offset) if store else []
                counts = store.count_items() if store else {"items_by_type": {}, "opportunities_by_type": {}}
                self._send(200, {"items": items, "count": len(items), **counts})
                return

            # 4. Run history API
            if path == "/api/runs":
                runs = store.list_runs() if store else []
                self._send(200, {"runs": runs, "count": len(runs)})
                return

            # 5. Source health API
            if path == "/api/sources":
                sources = source_report(config, store)
                self._send(200, {"sources": sources, "count": len(sources), "summary": summarize_sources(sources)})
                return

            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path not in {"/run", "/api/run"}:
                self._send(404, {"error": "not found"})
                return

            if not run_lock.acquire(blocking=False):
                self._send(409, {"error": "a radar run is already in progress"})
                return

            try:
                result = runner(config)
                self._send(200, result)
            except Exception as exc:
                self._send(500, {"error": f"radar run failed: {redact(exc)}"})
            finally:
                run_lock.release()

        def log_message(self, format: str, *args) -> None:
            print(f"radar-service: {format % args}")

    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="HTTP service for AI Tech Opportunity Radar.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    config = RadarConfig.from_env()
    server = make_server(args.host, args.port, config)
    print(f"AI Tech Opportunity Radar running on http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
