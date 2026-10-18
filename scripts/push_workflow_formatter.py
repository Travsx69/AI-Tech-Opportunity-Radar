"""Pushes the regenerated "Format Discord Digest" code to the live n8n workflow, changing nothing else.

    python scripts/push_workflow_formatter.py            # dry run: fetch, back up, build, assert
    python scripts/push_workflow_formatter.py --apply    # PUT as draft, read back, publish, verify

Builds from the *published* version (what the schedule runs), swaps only jsCode, uploads with
publishIfActive=false, verifies the read-back, then publishes that exact version. Rollback copies
of the draft and published versions are written to workflows/backup/ first.
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


def nodes_equal_except_code(a: list[dict], b: list[dict]) -> list[str]:
    """Names of nodes that differ beyond the Code node's jsCode (positions ignored)."""
    an, bn = {n["name"]: strip(n) for n in a}, {n["name"]: strip(n) for n in b}
    problems = sorted(set(an) ^ set(bn))
    for name in set(an) & set(bn):
        x, y = copy.deepcopy(an[name]), copy.deepcopy(bn[name])
        if name == CODE_NODE:
            x["parameters"].pop("jsCode", None)
            y["parameters"].pop("jsCode", None)
        if x != y:
            problems.append(name)
    return problems


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

    nodes = copy.deepcopy(published["nodes"])
    code_node = next(n for n in nodes if n["name"] == CODE_NODE)
    new_code = node_code()
    if code_node["parameters"].get("jsCode") == new_code:
        print("Live formatter already matches; nothing to do.")
        return 0
    code_node["parameters"]["jsCode"] = new_code
    body = {"name": draft["name"], "nodes": nodes, "connections": published["connections"], "settings": draft["settings"]}

    assert nodes_equal_except_code(nodes, published["nodes"]) == [], "only jsCode may differ from the published version"
    assert body["connections"] == published["connections"]
    print(f"built update: only {CODE_NODE}.jsCode changes ({len(new_code)} chars)")
    if not args.apply:
        print("dry run: no changes sent. Re-run with --apply.")
        return 0

    saved = api("PUT", f"/workflows/{WORKFLOW_ID}?publishIfActive=false", body)
    readback = api("GET", f"/workflows/{WORKFLOW_ID}")
    new_version = readback.get("versionId")
    rb_code = next(n for n in readback["nodes"] if n["name"] == CODE_NODE)["parameters"].get("jsCode")
    checks = {
        "draft has new code": rb_code == new_code,
        "no other node changed": nodes_equal_except_code(readback["nodes"], published["nodes"]) == [],
        "connections unchanged": readback["connections"] == published["connections"],
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
    live_code = next(n for n in live["nodes"] if n["name"] == CODE_NODE)["parameters"].get("jsCode")
    final = {
        "active": after.get("active") is True,
        "published version is the new draft": after.get("activeVersionId") == new_version,
        "published code is new code": live_code == new_code,
        "published nodes otherwise identical": nodes_equal_except_code(live["nodes"], published["nodes"]) == [],
        "schedule unchanged": [n["parameters"] for n in live["nodes"] if n["type"].endswith("scheduleTrigger")]
                              == [n["parameters"] for n in published["nodes"] if n["type"].endswith("scheduleTrigger")],
    }
    print("published:", json.dumps(final), f"old={active_id} new={after.get('activeVersionId')}")
    return 0 if all(final.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
