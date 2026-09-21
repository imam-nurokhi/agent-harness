"""The Friday management report is derived, never invented.

The plan requires "daily/weekly report deterministik ... dari data yang sudah
disetujui", so this report is computed from harness state rather than written
by an agent: it costs no engine spend, it cannot hallucinate a shipped task,
and the same input always renders the same text.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))
import weekly  # noqa: E402


NOW = 1789689600.0          # Fri 2026-09-18 08:00 UTC
DAY = 86400.0


def task(tid, status, mtime_days_ago, **kw):
    base = {"id": tid, "title": f"Title {tid}", "role": "backend", "project": "nexora",
            "status": status, "criteria_done": 1, "criteria_total": 2,
            "has_worktree": False, "mtime": NOW - mtime_days_ago * DAY}
    base.update(kw)
    return base


def job(jid, status, started_days_ago, **kw):
    base = {"id": jid, "status": status, "role": "backend", "task": "task-001",
            "elapsed": 12, "started": NOW - started_days_ago * DAY}
    base.update(kw)
    return base


def snapshot(tasks=(), services=(), engines=None):
    return {
        "tasks": list(tasks),
        "operations": {"services": list(services)},
        "engines": engines or {"chosen": "claude", "refused": {}},
        "summary": {"tasks_total": len(tasks)},
    }


class WindowTests(unittest.TestCase):
    def test_only_the_last_seven_days_count_as_this_week(self):
        data = weekly.collect(
            snapshot([task("task-001", "reported", 2), task("task-002", "reported", 30)]),
            [], now=NOW)
        self.assertEqual(["task-001"], [t["id"] for t in data["shipped"]])

    def test_the_window_edges_are_reported_so_the_reader_can_check_them(self):
        data = weekly.collect(snapshot(), [], now=NOW)
        self.assertIn("2026-09-11", data["period"])
        self.assertIn("2026-09-18", data["period"])


class ContentTests(unittest.TestCase):
    def test_work_in_flight_is_separated_from_work_not_started(self):
        data = weekly.collect(snapshot([
            task("task-001", "active", 0), task("task-002", "review", 0),
            task("task-003", "planned", 0)]), [], now=NOW)
        self.assertEqual(["task-001", "task-002"], [t["id"] for t in data["in_flight"]])
        self.assertEqual(["task-003"], [t["id"] for t in data["queued"]])

    def test_an_active_task_untouched_for_days_is_flagged_as_stuck(self):
        # The single thing a tech lead most needs surfaced before a management
        # meeting: work that looks in progress but has not moved.
        data = weekly.collect(snapshot([
            task("task-001", "active", 0), task("task-002", "active", 5)]), [], now=NOW)
        self.assertEqual(["task-002"], [t["id"] for t in data["stuck"]])

    def test_a_planned_task_sitting_still_is_not_called_stuck(self):
        # Nothing is expected to move in a task nobody has started.
        data = weekly.collect(snapshot([task("task-009", "planned", 40)]), [], now=NOW)
        self.assertEqual([], data["stuck"])

    def test_failed_runs_this_week_are_surfaced_with_their_task(self):
        data = weekly.collect(snapshot(), [job("j1", "failed", 1), job("j2", "done", 1),
                                           job("j3", "failed", 20)], now=NOW)
        self.assertEqual(["j1"], [j["id"] for j in data["failed_runs"]])
        self.assertEqual(1, data["runs_done"])

    def test_degraded_services_are_surfaced_and_healthy_ones_are_not(self):
        data = weekly.collect(snapshot(services=[
            {"id": "automation", "label": "n8n", "status": "ok"},
            {"id": "backup", "label": "daily backup", "status": "stale", "detail": "3 days old"},
        ]), [], now=NOW)
        self.assertEqual(["daily backup"], [s["label"] for s in data["attention"]])

    def test_a_refused_engine_is_a_delivery_risk_and_is_reported(self):
        data = weekly.collect(
            snapshot(engines={"chosen": "claude", "refused": {"claude": {"reason": "spend limit"}}}),
            [], now=NOW)
        self.assertIn("claude", str(data["engine_risks"]))


class RenderTests(unittest.TestCase):
    def test_an_empty_week_says_so_instead_of_inventing_progress(self):
        text = weekly.report(snapshot(), [], now=NOW)
        self.assertIn("tidak ada", text.lower())
        self.assertNotIn("None", text)

    def test_the_same_input_always_renders_the_same_report(self):
        snap = snapshot([task("task-001", "reported", 1), task("task-002", "active", 4)],
                        services=[{"id": "d", "label": "disk", "status": "warn"}])
        self.assertEqual(weekly.report(snap, [], now=NOW), weekly.report(snap, [], now=NOW))

    def test_task_titles_are_escaped_so_telegram_does_not_reject_the_message(self):
        snap = snapshot([task("task-001", "reported", 1, title="Fix <script> & co")])
        text = weekly.report(snap, [], now=NOW)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("&amp;", text)
        self.assertNotIn("<script>", text)

    def test_the_report_names_the_window_it_covers(self):
        self.assertIn("2026-09-18", weekly.report(snapshot(), [], now=NOW))

    def test_stuck_work_appears_in_the_rendered_report_not_only_in_the_data(self):
        snap = snapshot([task("task-007", "active", 6, title="Payment retry")])
        text = weekly.report(snap, [], now=NOW)
        self.assertIn("task-007", text)
        self.assertIn("Payment retry", text)


if __name__ == "__main__":
    unittest.main()


class TelegramWiringTests(unittest.TestCase):
    """The report is only useful if it is reachable from the chat."""

    def setUp(self):
        import importlib, os, tempfile
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        workspace = Path(self.tmp.name)
        for subdir in ("tasks", "reports", "roles", "claims"):
            (workspace / "agents" / subdir).mkdir(parents=True)
        (workspace / "worktrees").mkdir()
        (workspace / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(workspace)
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)
        self.tgcmd = importlib.import_module("tgcmd")
        self.tgcore = importlib.import_module("tgcore")
        self.tgbot = importlib.import_module("tgbot")

    def tearDown(self):
        import os
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()

    def test_weekly_is_dispatchable(self):
        self.assertIn("weekly", self.tgcmd.HANDLERS)

    def test_weekly_is_management_reporting_so_an_operator_may_read_it(self):
        # It is aggregate reporting, the same class as /reporting, not a
        # harness control.
        self.assertEqual("operator", self.tgbot.COMMAND_LEVELS.get("weekly"))

    def test_weekly_runs_against_a_real_empty_workspace_without_raising(self):
        text = self.tgcmd.cmd_weekly("")
        self.assertIn("Weekly report", text)

    def test_weekly_appears_in_help_and_in_the_slash_menu(self):
        self.assertIn("/weekly", self.tgcmd.cmd_help(""))
        self.assertIn("weekly", {name for name, _ in self.tgcore._full_command_list()})


class HonestyTests(unittest.TestCase):
    """The report must admit where its own evidence is weak."""

    def test_it_warns_when_the_window_swallows_nearly_every_reported_task(self):
        # "Completed this week" is derived from file mtime. After a bulk copy or
        # restore every mtime is recent, and the report would otherwise claim a
        # year of delivery as one week's work. Better to say so than to impress
        # a management meeting with a number that is an artefact of rsync.
        tasks = [task(f"task-{n:03d}", "reported", 1) for n in range(10)]
        data = weekly.collect(snapshot(tasks), [], now=NOW)
        self.assertTrue(data["mtime_suspect"])
        self.assertIn("mtime", weekly.render(data).lower())

    def test_a_normal_week_carries_no_such_warning(self):
        tasks = ([task(f"task-{n:03d}", "reported", 400) for n in range(10)]
                 + [task("task-new", "reported", 1)])
        data = weekly.collect(snapshot(tasks), [], now=NOW)
        self.assertFalse(data["mtime_suspect"])
        self.assertNotIn("artefak", weekly.render(data).lower())

    def test_a_week_with_no_reported_tasks_at_all_is_not_suspect(self):
        data = weekly.collect(snapshot([task("task-001", "planned", 1)]), [], now=NOW)
        self.assertFalse(data["mtime_suspect"])

    def test_long_lists_are_truncated_so_telegram_accepts_the_message(self):
        tasks = [task(f"task-{n:03d}", "planned", 1) for n in range(40)]
        text = weekly.report(snapshot(tasks), [], now=NOW)
        self.assertLess(len(text), 4096, "Telegram rejects messages over 4096 characters")
        self.assertIn("lainnya", text)

    def test_truncation_still_reports_the_true_total(self):
        tasks = [task(f"task-{n:03d}", "planned", 1) for n in range(40)]
        text = weekly.report(snapshot(tasks), [], now=NOW)
        self.assertIn("(40)", text)
