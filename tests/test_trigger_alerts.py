"""Scheduled work that fails silently is worse than no schedule at all.

These tests pin two alerts: a trigger that ran and failed, and a trigger that
never ran when it should have.
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "bin" / "lib"
ROOT = LIB.parents[1]
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


class OverdueTests(unittest.TestCase):
    """Schedule arithmetic, isolated from Telegram."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.old = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = self.tmp.name
        sys.modules.pop("trigmem", None)
        self.trigmem = importlib.import_module("trigmem")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.old
        self.tmp.cleanup()

    def test_daily_trigger_that_ran_this_morning_is_not_overdue(self):
        now = dt.datetime(2026, 9, 14, 12, 0)
        self.assertIsNone(self.trigmem.overdue("daily 07:00", "2026-09-14 07:01", now))

    def test_daily_trigger_that_last_ran_yesterday_is_overdue(self):
        now = dt.datetime(2026, 9, 14, 12, 0)
        missed = self.trigmem.overdue("daily 07:00", "2026-09-13 07:01", now)
        self.assertEqual(dt.datetime(2026, 9, 14, 7, 0), missed)

    def test_grace_period_stops_an_alert_the_moment_the_clock_ticks_past(self):
        now = dt.datetime(2026, 9, 14, 7, 5)
        self.assertIsNone(self.trigmem.overdue("daily 07:00", "2026-09-13 07:01", now))

    def test_weekly_trigger_uses_the_most_recent_matching_weekday(self):
        now = dt.datetime(2026, 9, 17, 12, 0)  # Thursday
        missed = self.trigmem.overdue("weekly Mon 09:00", "2026-09-07 09:00", now)
        self.assertEqual(dt.datetime(2026, 9, 14, 9, 0), missed)  # that Monday

    def test_never_run_is_overdue(self):
        now = dt.datetime(2026, 9, 14, 12, 0)
        self.assertIsNotNone(self.trigmem.overdue("daily 07:00", "", now))

    def test_unparseable_schedule_never_alerts(self):
        now = dt.datetime(2026, 9, 14, 12, 0)
        self.assertIsNone(self.trigmem.overdue("when the mood strikes", "", now))


class TriggerAlertTests(unittest.TestCase):
    """The Telegram-facing half: what actually gets pushed to the phone."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.tmp.name)
        for sub in ("tasks", "reports", "roles"):
            (self.workspace / "agents" / sub).mkdir(parents=True)
        (self.workspace / "worktrees").mkdir()
        self.old = os.environ.get("AH_WORKSPACE")
        self.old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["AH_WORKSPACE"] = str(self.workspace)
        # Isolated from the real machine: whether a trigger counts as installed
        # must be decided by the fixture, not by whatever units this host has.
        os.environ["XDG_CONFIG_HOME"] = str(self.workspace / ".config")
        for name in ("state", "trigmem", "tgcore", "tgcmd", "tgtask", "tgwatch", "jobs"):
            sys.modules.pop(name, None)
        self.state = importlib.import_module("state")
        self.trigmem = importlib.import_module("trigmem")
        self.tgwatch = importlib.import_module("tgwatch")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.old
        if self.old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self.old_xdg
        self.tmp.cleanup()

    def fresh(self) -> str:
        """A last_run that is never overdue, whatever day the suite is run.

        Hardcoding a date made these tests pass only on the day they were
        written: by the next morning the trigger was genuinely late and the
        overdue alert leaked into assertions about failure alerts.
        """
        stamp = (dt.datetime.now() - dt.timedelta(minutes=1))
        return stamp.strftime(self.trigmem.STAMP)

    def triggers(self, schedule="daily 07:00", last_run="") -> None:
        (self.workspace / "agents" / "triggers.json").write_text(json.dumps({
            "triggers": [{"id": "health", "role": "devops", "label": "Repo health",
                          "schedule": schedule, "last_run": last_run, "prompt": "x"}]
        }))

    def record(self, status: int, memo: str = "something broke") -> None:
        log = self.workspace / "agents" / "reports" / "trigger-health.log"
        log.write_text(f"MEMO: {memo}\n")
        self.trigmem.record("health", status, str(log))

    def test_failed_run_raises_one_alert_and_only_one(self):
        self.triggers(last_run=self.fresh())
        self.record(7)
        watch = {"jobs": {}, "tasks": {}, "triggers": {}}
        events = self.tgwatch.detect(watch)
        self.assertTrue(any("health" in e for e in events), events)
        self.assertTrue(any("something broke" in e for e in events), events)
        self.assertEqual([], [e for e in self.tgwatch.detect(watch) if "health" in e])

    def test_successful_run_is_silent(self):
        self.triggers(last_run=self.fresh())
        self.record(0, "all green")
        watch = {"jobs": {}, "tasks": {}, "triggers": {}}
        self.assertEqual([], [e for e in self.tgwatch.detect(watch) if "health" in e])

    def _install(self, tid: str = "health") -> None:
        """Mark the trigger as actually scheduled.

        Since 2026-09-21 an overdue alert requires an installed trigger: one
        the owner chose not to install cannot run, so it cannot be late (see
        tests/test_trigger_installed_detection.py). This fixture therefore has
        to say which world it is testing.
        """
        unit = Path(os.environ["XDG_CONFIG_HOME"]) / "systemd" / "user"
        unit.mkdir(parents=True, exist_ok=True)
        (unit / f"com.ah.trigger.{tid}.timer").write_text("[Timer]\n")

    def test_an_installed_trigger_that_never_fired_is_reported_overdue_once(self):
        self.triggers(schedule="daily 07:00", last_run="2020-01-01 07:00")
        self._install()
        watch = {"jobs": {}, "tasks": {}, "triggers": {}}
        events = [e for e in self.tgwatch.detect(watch) if "health" in e]
        self.assertEqual(1, len(events), events)
        self.assertIn("terlambat", events[0].lower())
        self.assertEqual([], [e for e in self.tgwatch.detect(watch) if "health" in e])

    def test_upgrading_an_older_watch_file_announces_nothing_the_first_time(self):
        """An existing bot has a watch file with no trigger baseline at all."""
        self.triggers(last_run="2020-01-01 07:00")
        self.record(7)
        legacy = {"jobs": {}, "tasks": {}, "primed": True}   # no "triggers" key
        self.assertEqual([], self.tgwatch.detect(legacy))
        self.assertIn("triggers", legacy)

    def test_priming_swallows_history_so_a_restart_is_not_a_flood(self):
        self.triggers(last_run="2020-01-01 07:00")
        self.record(7)
        watch = self.tgwatch.load()
        self.tgwatch.prime(watch)
        self.assertEqual([], [e for e in self.tgwatch.detect(watch) if "health" in e])


if __name__ == "__main__":
    unittest.main()
