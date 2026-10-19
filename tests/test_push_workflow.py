import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from push_workflow_formatter import CODE_NODE, expected_workflow, node_diff  # noqa: E402


def sched(name, cron):
    return {"name": name, "type": "n8n-nodes-base.scheduleTrigger", "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}}, "position": [0, 0]}


class PushWorkflowTests(unittest.TestCase):
    def test_only_code_and_schedule_change_and_connections_follow_rename(self):
        http = {"name": "Run", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "u"}, "position": [1, 1]}
        code = {"name": CODE_NODE, "type": "n8n-nodes-base.code", "parameters": {"jsCode": "old", "mode": "runOnceForAllItems"}, "position": [2, 2]}
        published = {"nodes": [sched("Daily at 6 AM", "0 6 * * *"), http, code],
                     "connections": {"Daily at 6 AM": {"main": [[{"node": "Run"}]]}, "Run": {"main": [[{"node": CODE_NODE}]]}}}
        repo = {"nodes": [sched("Daily at 10 PM", "0 22 * * *")]}

        nodes, connections = expected_workflow(published, repo, "new")

        self.assertEqual(sorted(node_diff(nodes, published["nodes"])), sorted([CODE_NODE, "Daily at 10 PM", "Daily at 6 AM"]))
        by_name = {n["name"]: n for n in nodes}
        self.assertEqual(by_name[CODE_NODE]["parameters"], {"jsCode": "new", "mode": "runOnceForAllItems"})
        self.assertEqual(by_name["Daily at 10 PM"]["parameters"]["rule"]["interval"][0]["expression"], "0 22 * * *")
        self.assertEqual(by_name["Run"], http)
        self.assertEqual(connections, {"Daily at 10 PM": {"main": [[{"node": "Run"}]]}, "Run": {"main": [[{"node": CODE_NODE}]]}})
        self.assertEqual(published["nodes"][0]["name"], "Daily at 6 AM")  # input not mutated


if __name__ == "__main__":
    unittest.main()
