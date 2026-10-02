"""Work that has stopped moving should say so, not wait for Friday.

The weekly report has a "mandek" section, but a task that stalls on Monday then
goes unmentioned until Friday has cost four days. tgwatch already notices runs
that finish and criteria that complete -- both are *progress*. Nothing noticed
the absence of progress.

Deterministic and derived from mtime, so it costs no engine spend.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))

DAY = 86400.0


class StuckTaskAlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.tmp.name)
        for subdir in ("tasks", "reports", "roles", "claims"):
            (self.workspace / "agents" / subdir).mkdir(parents=True)
        (self.workspace / "worktrees").mkdir()
        (self.workspace / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.workspace)
        for name in ("state", "jobs", "tgcore", "tgwatch", "trigmem"):
            sys.modules.pop(name, None)
        self.tgwatch = importlib.import_module("tgwatch")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()

    def task(self, tid, status_active=True, days_old=0.0):
        """Write a task file and age it."""
        body = f"# Task: {tid} title\n\nRole: backend\n\n## Acceptance criteria\n- [ ] one\n"
        f = self.workspace / "agents" / "tasks" / f"{tid}.md"
        f.write_text(body)
        if status_active:
            # A worktree with no report is what makes a task "active".
            (self.workspace / "worktrees" / tid).mkdir(parents=True, exist_ok=True)
        old = time.time() - days_old * DAY
        os.utime(f, (old, old))
        return f

    def stuck(self, w=None):
        return self.tgwatch._stuck_task_events(w if w is not None else {})

    def test_an_active_task_untouched_for_days_raises_an_alert(self):
        self.task("task-001", days_old=5)
        events = self.stuck()
        self.assertEqual(1, len(events))
        self.assertIn("task-001", events[0])

    def test_a_task_touched_today_raises_nothing(self):
        self.task("task-002", days_old=0)
        self.assertEqual([], self.stuck())

    def test_a_task_with_no_worktree_and_no_report_is_not_called_stuck(self):
        # Planned work sitting in the backlog is not a stall.
        self.task("task-003", status_active=False, days_old=40)
        self.assertEqual([], self.stuck())

    def test_the_alert_names_how_long_it_has_been_still(self):
        self.task("task-004", days_old=9)
        self.assertIn("9", self.stuck()[0])

    def test_it_does_not_repeat_the_same_alert_on_every_poll(self):
        # tgwatch runs every 25 seconds; an alert per poll is noise, not signal.
        self.task("task-005", days_old=4)
        w = {}
        self.assertEqual(1, len(self.stuck(w)))
        self.assertEqual([], self.stuck(w))

    def test_it_speaks_again_once_a_day_has_passed(self):
        self.task("task-006", days_old=4)
        w = {}
        self.assertEqual(1, len(self.stuck(w)))
        w["stuck"]["task-006"] = w["stuck"]["task-006"] - DAY - 1
        self.assertEqual(1, len(self.stuck(w)))

    def test_a_task_that_starts_moving_again_is_forgotten(self):
        # so that stalling a second time alerts again immediately
        f = self.task("task-007", days_old=4)
        w = {}
        self.stuck(w)
        self.assertIn("task-007", w["stuck"])
        now = time.time()
        os.utime(f, (now, now))
        self.stuck(w)
        self.assertNotIn("task-007", w["stuck"])

    def test_the_detector_is_wired_into_the_notification_sweep(self):
        self.task("task-008", days_old=6)
        w = self.tgwatch.load()
        self.tgwatch.prime(w)
        events = self.tgwatch.detect(w)
        self.assertTrue(any("task-008" in e for e in events),
                        "stuck alert never reaches the chat")


if __name__ == "__main__":
    unittest.main()
