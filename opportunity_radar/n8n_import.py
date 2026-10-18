from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PUBLIC_CREATE_FIELDS = ("name", "nodes", "connections", "settings")


def build_create_payload(workflow: dict[str, Any]) -> dict[str, Any]:
    return {field: workflow[field] for field in PUBLIC_CREATE_FIELDS}


def request_json(url: str, api_key: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={"X-N8N-API-KEY": api_key, "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"n8n API HTTP {exc.code}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"n8n API request failed: {exc}") from exc


def main() -> int:
    api_key = (os.getenv("N8N_API_KEY") or "").strip()
    if not api_key:
        print("N8N_API_KEY is not set. No changes were made.")
        return 2
    base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")
    workflow_path = Path(__file__).resolve().parents[1] / "workflows" / "github-mvp.n8n.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    existing = request_json(f"{base_url}/api/v1/workflows?limit=100", api_key)
    for item in existing.get("data", []):
        if item.get("name") == workflow["name"]:
            print(f"Workflow already exists; no duplicate created. id={item.get('id')}")
            return 0
    created = request_json(
        f"{base_url}/api/v1/workflows",
        api_key,
        method="POST",
        payload=build_create_payload(workflow),
    )
    workflow_id = created.get("id")
    if not workflow_id:
        raise RuntimeError("n8n API did not return a workflow id")
    verified = request_json(f"{base_url}/api/v1/workflows/{workflow_id}", api_key)
    if verified.get("name") != workflow["name"]:
        raise RuntimeError("n8n workflow read-back verification failed")
    print(f"Created inactive workflow and verified read-back. id={workflow_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
