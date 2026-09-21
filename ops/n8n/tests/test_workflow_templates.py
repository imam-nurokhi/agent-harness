"""Workflow templates must remain reviewable and inert before owner approval."""
from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "workflow-templates"


class WorkflowTemplateTests(unittest.TestCase):
    def test_github_daily_status_template_is_disabled_and_read_only(self):
        workflow = json.loads(
            (TEMPLATES / "github-read-only-daily-status.json").read_text()
        )

        self.assertFalse(workflow["active"])
        self.assertEqual("manual", workflow["tags"][0]["name"])
        self.assertTrue(any(node["type"] == "n8n-nodes-base.manualTrigger"
                            for node in workflow["nodes"]))
        self.assertFalse(any("executeCommand" in node["type"] or ".ssh" in node["type"]
                             or "readWriteFile" in node["type"] or ".code" in node["type"]
                             for node in workflow["nodes"]))

    def test_github_requests_are_limited_to_read_only_api_endpoints(self):
        workflow = json.loads(
            (TEMPLATES / "github-read-only-daily-status.json").read_text()
        )
        requests = [node for node in workflow["nodes"]
                    if node["type"] == "n8n-nodes-base.httpRequest"]

        self.assertEqual(3, len(requests))
        for node in requests:
            self.assertEqual("GET", node["parameters"]["method"])
            self.assertTrue(node["parameters"]["url"].startswith("https://api.github.com/"))
            self.assertEqual("predefinedCredentialType", node["parameters"]["authentication"])
            self.assertEqual("githubApi", node["parameters"]["nodeCredentialType"])


if __name__ == "__main__":
    unittest.main()
