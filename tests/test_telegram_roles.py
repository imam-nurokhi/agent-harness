"""Per-chat Telegram roles protect detailed data and harness controls."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "bin" / "lib"
sys.path.insert(0, str(LIB))


class TelegramRoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.tmp.name)
        for subdir in ("tasks", "reports", "roles", "claims"):
            (self.workspace / "agents" / subdir).mkdir(parents=True)
        (self.workspace / "worktrees").mkdir()
        (self.workspace / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.workspace)
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)
        self.tgcore = importlib.import_module("tgcore")
        self.tgcmd = importlib.import_module("tgcmd")
        self.tgtask = importlib.import_module("tgtask")
        self.tgbot = importlib.import_module("tgbot")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)

    def test_legacy_paired_chat_remains_owner(self):
        self.assertEqual("owner", self.tgcore.role_for({"allowed": [101]}, 101))
        self.assertTrue(self.tgcore.has_level({"allowed": [101]}, 101, "owner"))

    def test_viewer_can_read_status_but_cannot_start_agent(self):
        cfg = {"allowed": [101], "roles": {"101": "viewer"}}
        sent = []
        status = Mock(return_value="STATUS")
        run = Mock(return_value="RUN")
        with patch.object(self.tgcore, "send", side_effect=lambda *args: sent.append(args)), \
             patch.dict(self.tgcmd.HANDLERS, {"status": status, "run": run}):
            self.tgbot._dispatch(cfg, {"chat": {"id": 101, "username": "viewer"},
                                       "text": "/status"})
            self.tgbot._dispatch(cfg, {"chat": {"id": 101, "username": "viewer"},
                                       "text": "/run backend task-001"})
        status.assert_called_once_with("")
        run.assert_not_called()
        self.assertTrue(any("memerlukan role" in message and "owner" in message
                            for _, message, *rest in sent))

    def test_owner_can_grant_operator_without_exposing_owner_controls(self):
        cfg = {"allowed": [101, 202], "roles": {"101": "owner", "202": "viewer"}}
        response = self.tgbot._handle_grant(cfg, 101, "202 operator")
        self.assertIn("operator", response)
        self.assertEqual("operator", self.tgcore.role_for(cfg, 202))
        self.assertFalse(self.tgcore.has_level(cfg, 202, "owner"))

    def test_last_owner_cannot_demote_themself(self):
        cfg = {"allowed": [101], "roles": {"101": "owner"}}
        response = self.tgbot._handle_grant(cfg, 101, "101 viewer")
        self.assertIn("owner terakhir", response)
        self.assertEqual("owner", self.tgcore.role_for(cfg, 101))

    def test_new_pair_becomes_viewer_when_an_owner_already_exists(self):
        cfg = {"allowed": [101], "roles": {"101": "owner"}, "pair_code": "123456"}
        with patch.object(self.tgcore, "save_config"):
            self.tgbot._handle_pair(cfg, 202, "123456", "new-viewer")
        self.assertEqual("viewer", self.tgcore.role_for(cfg, 202))


if __name__ == "__main__":
    unittest.main()
