"""Pushes the repo's Discord formatter code and schedule trigger to the live n8n workflow, changing nothing else.

    python scripts/push_workflow_formatter.py            # dry run: fetch, back up, build, assert
    python scripts/push_workflow_formatter.py --apply    # PUT as draft, read back, publish, verify

Builds from the *published* version (what the schedule runs) and replaces only the
"Format Discord Digest" jsCode (from scripts/discord_digest.js) and the schedule trigger's name and
parameters (from workflows/github-mvp.n8n.json). Uploads with publishIfActive=false, verifies the
read-back equals that expected workflow, then publishes that exact version. Rollback copies of the
draft and published versions are written to workflows/backup/ first.
Needs N8N_API_KEY (and optional N8N_BASE_URL). Stdlib only.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_workflow_code import node_code  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = "13oxoQeASaKIsu74"
CODE_NODE = "Format Discord Digest"


def api(method: str, path: str, body: dict | None = None) -> dict:
    base = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")
    key = (os.getenv("N8N_API_KEY") or "").strip()
    if not key:
        sys.exit("N8N_API_KEY is not set. No changes were made.")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(f"{base}/api/v1{path}", data=data, method=method,
                      headers={"X-N8N-API-KEY": key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"n8n API {method} {path} -> HTTP {exc.code}: {detail}") from exc


def strip(node: dict) -> dict:
    return {k: v for k, v in node.items() if k != "position"}


def node_diff(a: list[dict], b: list[dict]) -> list[str]:
    """Names of nodes that differ between two node lists (positions ignored)."""
    an, bn = {n["name"]: strip(n) for n in a}, {n["name"]: strip(n) for n in b}
    return sorted(set(an) ^ set(bn)) + sorted(n for n in set(an) & set(bn) if an[n] != bn[n])


def is_schedule(node: dict) -> bool:
    return node["type"].endswith("scheduleTrigger")


def expected_workflow(published: dict, repo: dict, code: str) -> tuple[list[dict], dict]:
    """The published nodes/connections with only the formatter code and the schedule trigger replaced."""
    nodes, connections = copy.deepcopy(published["nodes"]), copy.deepcopy(published["connections"])
    next(n for n in nodes if n["name"] == CODE_NODE)["parameters"]["jsCode"] = code
    live_sched, repo_sched = next(n for n in nodes if is_schedule(n)), next(n for n in repo["nodes"] if is_schedule(n))
    if live_sched["name"] != repo_sched["name"]:  # connections are keyed by node name
        connections[repo_sched["name"]] = connections.pop(live_sched["name"])
    live_sched["name"], live_sched["parameters"] = repo_sched["name"], copy.deepcopy(repo_sched["parameters"])
    return nodes, connections


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    draft = api("GET", f"/workflows/{WORKFLOW_ID}")
    active_id = draft.get("activeVersionId")
    if not draft.get("active") or not active_id:
        raise SystemExit("Workflow is not active/published; refusing to change it.")
    published = api("GET", f"/workflows/{WORKFLOW_ID}/{active_id}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = ROOT / "workflows" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / f"{WORKFLOW_ID}-draft-{stamp}.json").write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
    (backup_dir / f"{WORKFLOW_ID}-published-{active_id}-{stamp}.json").write_text(json.dumps(published, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"rollback copies saved in workflows/backup/ (published version {active_id})")

    repo = json.loads((ROOT / "workflows" / "github-mvp.n8n.json").read_text(encoding="utf-8"))
    nodes, connections = expected_workflow(published, repo, node_code())
    changed = node_diff(nodes, published["nodes"])
    if not changed:
        print("Live workflow already matches the repo; nothing to do.")
        return 0
    allowed = {CODE_NODE} | {n["name"] for n in published["nodes"] + nodes if is_schedule(n)}
    assert set(changed) <= allowed, f"unexpected node changes: {changed}"
    body = {"name": draft["name"], "nodes": nodes, "connections": connections, "settings": draft["settings"]}
    print(f"built update: changes {changed}")
    if not args.apply:
        print("dry run: no changes sent. Re-run with --apply.")
        return 0

    api("PUT", f"/workflows/{WORKFLOW_ID}?publishIfActive=false", body)
    readback = api("GET", f"/workflows/{WORKFLOW_ID}")
    new_version = readback.get("versionId")
    checks = {
        "draft equals expected nodes": node_diff(readback["nodes"], nodes) == [],
        "draft connections as expected": readback["connections"] == connections,
        "live version untouched before publish": readback.get("activeVersionId") == active_id,
        "still active": readback.get("active") is True,
        "new draft version created": bool(new_version) and new_version != draft.get("versionId"),
    }
    print("draft read-back:", json.dumps(checks))
    if not all(checks.values()):
        raise SystemExit("Draft verification failed; NOT publishing. Live version is unchanged.")

    # n8n 2.37 spec: /activate publishes a specific version ({versionId}); /publish is mentioned but not defined.
    api("POST", f"/workflows/{WORKFLOW_ID}/activate", {"versionId": new_version})
    after = api("GET", f"/workflows/{WORKFLOW_ID}")
    live = api("GET", f"/workflows/{WORKFLOW_ID}/{after.get('activeVersionId')}")
    final = {
        "active": after.get("active") is True,
        "published version is the new draft": after.get("activeVersionId") == new_version,
        "published nodes equal expected": node_diff(live["nodes"], nodes) == [],
        "published connections as expected": live["connections"] == connections,
        "schedule": [n["parameters"] for n in live["nodes"] if is_schedule(n)],
    }
    print("published:", json.dumps(final), f"old={active_id} new={after.get('activeVersionId')}")
    return 0 if all(final.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
