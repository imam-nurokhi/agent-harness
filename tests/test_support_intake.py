"""Internal support intake is bounded, auditable, and rejects likely secrets."""
from __future__ import annotations

import importlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class SupportIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.tmp.name)
        for directory in ("tasks", "reports", "roles", "claims"):
            (self.root / "agents" / directory).mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        (self.root / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.root)
        for name in ("state", "support"):
            sys.modules.pop(name, None)
        self.support = importlib.import_module("support")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()
        for name in ("state", "support"):
            sys.modules.pop(name, None)

    def test_create_assigns_id_sla_and_private_storage(self):
        request = self.support.create({
            "subject": "Login issue after password reset",
            "requester_ref": "Client ticket CX-104",
            "summary": "User sees an error page after resetting access.",
            "severity": "high",
        })
        self.assertEqual("sup-0001", request["id"])
        self.assertEqual("new", request["status"])
        self.assertEqual("high", request["severity"])
        self.assertTrue(request["sla_due_at"])
        self.assertEqual([request], self.support.list_requests())
        self.assertEqual(0o600, stat.S_IMODE(self.support.INTAKE.stat().st_mode))

    def test_rejects_likely_secret_material(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            self.support.create({
                "subject": "Cannot connect",
                "requester_ref": "Ticket CX-105",
                "summary": "Here is my api_key=super-secret-value",
                "severity": "normal",
            })

    def test_handoff_and_status_transition_are_explicit(self):
        created = self.support.create({
            "subject": "Certificate question",
            "requester_ref": "Ticket CX-106",
            "summary": "Customer requests certificate delivery status.",
            "severity": "normal",
        })
        updated = self.support.update(created["id"], status="assigned", assignee="Support Team")
        self.assertEqual("assigned", updated["status"])
        self.assertEqual("Support Team", updated["assignee"])


if __name__ == "__main__":
    unittest.main()
