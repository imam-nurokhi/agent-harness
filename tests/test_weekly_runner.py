"""The scheduled weekly report must leave a durable artefact, not only a chat.

A management meeting needs something to point at afterwards, and a Telegram
message that failed to send must not silently lose the week's report.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class WeeklyRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.tmp.name)
        for subdir in ("tasks", "reports", "roles", "claims"):
            (self.workspace / "agents" / subdir).mkdir(parents=True)
        (self.workspace / "worktrees").mkdir()
        (self.workspace / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.workspace)
        for name in ("state", "jobs", "tgcore", "tgcmd", "weekly", "weeklyrun"):
            sys.modules.pop(name, None)
        self.weeklyrun = importlib.import_module("weeklyrun")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()

    def reports(self):
        return sorted((self.workspace / "agents" / "reports").glob("weekly-*.md"))

    def test_it_writes_the_report_to_disk(self):
        with patch.object(self.weeklyrun.tgcore, "notification_targets", return_value=[]):
            self.weeklyrun.main()
        self.assertEqual(1, len(self.reports()))
        self.assertIn("Weekly report", self.reports()[0].read_text())

    def test_the_written_report_is_markdown_not_telegram_html(self):
        # The file is for humans and for the repo, so it must not be littered
        # with <b> and <code> tags.
        with patch.object(self.weeklyrun.tgcore, "notification_targets", return_value=[]):
            self.weeklyrun.main()
        text = self.reports()[0].read_text()
        self.assertNotIn("<b>", text)
        self.assertNotIn("<code>", text)

    def test_it_sends_the_report_to_every_notification_target(self):
        sent = []
        with patch.object(self.weeklyrun.tgcore, "notification_targets", return_value=[11, 22]), \
             patch.object(self.weeklyrun.tgcore, "send",
                          side_effect=lambda c, m: sent.append(c) or {"ok": True}):
            self.weeklyrun.main()
        self.assertEqual([11, 22], sent)

    def test_the_file_still_exists_when_telegram_delivery_fails(self):
        with patch.object(self.weeklyrun.tgcore, "notification_targets", return_value=[11]), \
             patch.object(self.weeklyrun.tgcore, "send", side_effect=RuntimeError("network")):
            self.weeklyrun.main()
        self.assertEqual(1, len(self.reports()), "the week's report was lost with the send")

    def test_running_twice_in_a_day_does_not_pile_up_files(self):
        with patch.object(self.weeklyrun.tgcore, "notification_targets", return_value=[]):
            self.weeklyrun.main()
            self.weeklyrun.main()
        self.assertEqual(1, len(self.reports()))


if __name__ == "__main__":
    unittest.main()
