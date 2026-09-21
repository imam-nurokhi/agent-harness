"""Read-only Telegram commands for the cloud operations control surface."""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class TelegramOperationsCommandsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        (self.root / "agents" / "roles").mkdir(parents=True)
        (self.root / "agents" / "claims").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        (self.root / "AGENTS.md").write_text("rules")
        self.old = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.root)
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgwatch"):
            sys.modules.pop(name, None)
        self.tgcmd = importlib.import_module("tgcmd")
        self.tgcore = importlib.import_module("tgcore")

    def tearDown(self):
        self._tmp.cleanup()
        if self.old is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.old
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgwatch"):
            sys.modules.pop(name, None)

    def _snapshot(self):
        return {
            "summary": {
                "tasks_total": 6,
                "by_status": {"planned": 2, "active": 2, "review": 1, "reported": 1},
            },
            "operations": {"services": [
                {"id": "automation", "label": "n8n automation", "status": "ok",
                 "detail": "loopback verified"},
                {"id": "backup", "label": "daily local backup", "status": "ok",
                 "detail": "systemd timer active"},
            ]},
        }

    def test_new_operations_commands_are_registered_and_visible(self):
        for command in ("ops", "brief", "reporting", "sources", "reminders", "support", "deploy"):
            self.assertIn(command, self.tgcmd.HANDLERS)
        names = [name for name, _ in self.tgcore._full_command_list()]
        self.assertIn("ops", names)
        self.assertIn("reporting", names)

    def test_ops_is_read_only_and_never_contains_credentials(self):
        with patch.object(self.tgcmd.state, "snapshot", return_value=self._snapshot()):
            out = self.tgcmd.cmd_ops("")
        self.assertIn("n8n automation", out)
        self.assertIn("https://agents.nexoratech.co/automation/", out)
        self.assertNotIn("password", out.lower())
        self.assertNotIn("token", out.lower())

    def test_reporting_rejects_unknown_audience_and_stays_aggregate(self):
        with patch.object(self.tgcmd.state, "snapshot", return_value=self._snapshot()):
            out = self.tgcmd.cmd_reporting("management")
            invalid = self.tgcmd.cmd_reporting("sales")
        self.assertIn("6", out)
        self.assertNotIn("task-", out)
        self.assertIn("director", invalid)

    def test_deploy_is_an_explicit_production_guardrail(self):
        out = self.tgcmd.cmd_deploy("production")
        self.assertIn("GitHub Environment", out)
        self.assertIn("tidak", out.lower())
        self.assertNotIn("subprocess", out.lower())

    def test_sources_are_honest_about_unconnected_systems(self):
        with patch.object(self.tgcmd.state, "snapshot", return_value=self._snapshot()):
            out = self.tgcmd.cmd_sources("")
        self.assertIn("GitHub", out)
        self.assertIn("belum", out.lower())


if __name__ == "__main__":
    unittest.main()
