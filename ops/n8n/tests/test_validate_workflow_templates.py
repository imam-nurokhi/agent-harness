"""The review manifest is a fail-closed gate for workflow template imports."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import validate_workflow_templates  # noqa: E402


class ValidateWorkflowTemplatesTests(unittest.TestCase):
    def test_review_manifest_and_templates_are_accepted(self):
        self.assertEqual([], validate_workflow_templates.validate(ROOT / "workflow-templates"))

    def test_active_workflow_is_rejected_even_when_manifest_says_review(self):
        with tempfile.TemporaryDirectory() as directory:
            templates = Path(directory)
            workflow = json.loads((ROOT / "workflow-templates" /
                                   "github-read-only-daily-status.json").read_text())
            workflow["active"] = True
            (templates / "github-read-only-daily-status.json").write_text(json.dumps(workflow))
            (templates / "manifest.json").write_text(
                (ROOT / "workflow-templates" / "manifest.json").read_text()
            )
            errors = validate_workflow_templates.validate(templates)
        self.assertIn("github-read-only-daily-status must remain inactive until owner approval", errors)

    def test_template_without_manifest_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            templates = Path(directory)
            workflow = json.loads((ROOT / "workflow-templates" /
                                   "github-read-only-daily-status.json").read_text())
            (templates / "github-read-only-daily-status.json").write_text(json.dumps(workflow))
            (templates / "manifest.json").write_text('{"templates": []}')
            errors = validate_workflow_templates.validate(templates)
        self.assertIn("github-read-only-daily-status.json is missing from manifest", errors)


if __name__ == "__main__":
    unittest.main()
