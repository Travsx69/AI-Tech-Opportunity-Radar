"""Copies scripts/discord_digest.js into the n8n workflow's "Format Discord Digest" Code node.

    python scripts/sync_workflow_code.py [--from-live data/workflow-live.json]

--from-live rebuilds the workflow file from an n8n API export so schedule, credentials, and node
layout match what is actually deployed. Nothing is sent to n8n; see README for the update step.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "github-mvp.n8n.json"
SCRIPT = ROOT / "scripts" / "discord_digest.js"
N8N_TAIL = """

const radarResult = $input.first().json;
const messages = formatDiscordDigest(radarResult);
return messages.map((content, index) => ({
  json: {
    content,
    digest_part: index + 1,
    digest_parts: messages.length,
    radar_result: radarResult,
  },
}));
"""


def node_code() -> str:
    body = SCRIPT.read_text(encoding="utf-8").split("module.exports", 1)[0].rstrip()
    return body + "\n" + N8N_TAIL


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-live", type=Path)
    args = parser.parse_args()
    if args.from_live:
        live = json.loads(args.from_live.read_text(encoding="utf-8"))
        live = live[0] if isinstance(live, list) else live
        workflow = {
            "id": live["id"],
            "name": live["name"],
            "nodes": live["nodes"],
            "connections": live["connections"],
            "settings": {k: v for k, v in live["settings"].items() if k in {"timezone", "executionOrder"}},
            "active": False,  # the file never activates anything; the live instance keeps its own state
        }
    else:
        workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    node = next(n for n in workflow["nodes"] if n["name"] == "Format Discord Digest")
    node["parameters"]["jsCode"] = node_code()
    WORKFLOW.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {WORKFLOW.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
