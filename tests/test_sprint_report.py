"""The daily sprint report must be right without anyone reading it.

It fires at 07:30 WIB on a weekday and its output goes straight to the owner's
phone, so nobody proofreads it first. These tests pin the parts that would be
wrong quietly: which sprints it picks, what counts as unfinished, and the fact
that it admits the Slack half is missing instead of implying it was included.

Everything here is pure — no browser, no network. The Playwright read has no
test because a test that needs a live login and a real session is not a test.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import sprint_report as sr  # noqa: E402


def task(title, status="development", user_id=15, points=3, project="Audit"):
    return {"task": {"title": title, "status": status, "total_points": points,
                     "assignees": [{"user_id": user_id}]},
            "project": {"name": project}}


def sprint(sid, name, status, start, end, tasks=(), **summary):
    return {"sprint": {"id": sid, "name": name, "status": status,
                       "start_date": start, "end_date": end, "tasks": list(tasks)},
            "summary": summary}


SPRINTS = [
    sprint(1, "Sprint 1", "completed", "2026-08-18", "2026-08-28",
           progress=88, done_tasks=24, total_tasks=27, done_points=13, total_points=26),
    sprint(2, "Sprint 2", "completed", "2026-08-31", "2026-09-11",
           tasks=[task("Paragraf certificate", "uat"), task("Link certificate", "review")],
           progress=80, done_tasks=28, total_tasks=35, done_points=101, total_points=123),
    sprint(3, "Sprint 3", "active", "2026-09-15", "2026-09-25",
           tasks=[task("Setup CI/CD", "todo", 22, 5, "KMS"),
                  task("DevOps OneAlpha-v2", "development", 16, 5, "Superapp"),
                  task("Setup repo", "done", 15, 1, "Superapp")],
           progress=70, done_tasks=12, total_tasks=17, done_points=33,
           total_points=64, overdue_tasks=2),
]


class SprintSelectionTests(unittest.TestCase):
    def test_it_picks_the_active_sprint_and_the_last_completed_one(self):
        active, completed = sr.active_and_last_completed(SPRINTS)
        self.assertEqual(active["name"], "Sprint 3")
        self.assertEqual(completed["name"], "Sprint 2")

    def test_selection_is_by_status_and_date_not_by_name(self):
        # Renaming a sprint must not break the report.
        renamed = [sprint(9, "Iterasi Q4", "active", "2026-10-01", "2026-10-10")]
        active, _ = sr.active_and_last_completed(renamed)
        self.assertEqual(active["name"], "Iterasi Q4")

    def test_no_sprints_at_all_is_handled(self):
        self.assertEqual(sr.active_and_last_completed([]), (None, None))
        self.assertIn("Tidak ada sprint", sr.build_message([]))


class OpenTaskTests(unittest.TestCase):
    def test_done_tasks_are_not_listed_as_open(self):
        titles = [t["title"] for t in sr.open_tasks(SPRINTS[2]["sprint"])]
        self.assertNotIn("Setup repo", titles)
        self.assertEqual(len(titles), 2)

    def test_heaviest_work_is_listed_first(self):
        s = sprint(4, "S", "active", "", "", tasks=[
            task("kecil", "todo", 15, 1), task("besar", "todo", 15, 13)])
        self.assertEqual(sr.open_tasks(s["sprint"])[0]["title"], "besar")

    def test_assignees_are_named_not_numbered(self):
        who = sr.open_tasks(SPRINTS[2]["sprint"])[0]["who"]
        self.assertIn(who, ("Diky", "Rafly"))

    def test_an_unknown_user_id_is_shown_plainly_not_dropped(self):
        s = sprint(5, "S", "active", "", "", tasks=[task("x", "todo", 999, 1)])
        self.assertIn("999", sr.open_tasks(s["sprint"])[0]["who"])

    def test_a_task_with_no_assignee_does_not_crash(self):
        s = {"tasks": [{"task": {"title": "x", "status": "todo"}, "project": {}}]}
        self.assertEqual(sr.open_tasks(s)[0]["who"], "—")


class MessageTests(unittest.TestCase):
    def setUp(self):
        self.msg = sr.build_message(SPRINTS, has_slack_token=False)

    def test_the_active_sprint_numbers_are_present(self):
        self.assertIn("Sprint 3", self.msg)
        self.assertIn("12/17", self.msg)
        self.assertIn("33/64", self.msg)
        self.assertIn("70%", self.msg)

    def test_overdue_work_is_called_out(self):
        self.assertIn("2 tugas lewat tenggat", self.msg)

    def test_the_finished_sprint_carry_over_is_summarised(self):
        self.assertIn("Sprint 2", self.msg)
        self.assertIn("Sisa 2 tugas", self.msg)

    def test_the_missing_slack_half_is_admitted(self):
        # Silence here would let the owner believe Slack was read and had
        # nothing to say.
        self.assertIn("SLACK_BOT_TOKEN", self.msg)

    def test_no_slack_disclaimer_once_the_token_exists(self):
        self.assertNotIn("SLACK_BOT_TOKEN",
                         sr.build_message(SPRINTS, has_slack_token=True))

    def test_html_in_a_task_title_cannot_break_the_message(self):
        s = [sprint(6, "S<b>", "active", "", "", tasks=[task("<script>x", "todo")],
                    progress=1, done_tasks=0, total_tasks=1)]
        out = sr.build_message(s)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>", out)

    def test_the_list_is_capped_so_the_message_fits_telegram(self):
        many = [task(f"tugas {i}", "todo", 15, 1) for i in range(30)]
        s = [sprint(7, "S", "active", "", "", tasks=many,
                    progress=0, done_tasks=0, total_tasks=30)]
        out = sr.build_message(s, limit=6)
        self.assertIn("dan 24 lagi", out)
        self.assertLess(len(out), 4000)


class EnvTests(unittest.TestCase):
    def test_env_prefers_the_process_environment(self):
        sr.os.environ["NEXONE_EMAIL"] = "from-env@example.com"
        self.addCleanup(lambda: sr.os.environ.pop("NEXONE_EMAIL", None))
        self.assertEqual(sr.env("NEXONE_EMAIL"), "from-env@example.com")

    def test_a_missing_key_is_empty_not_an_exception(self):
        self.assertEqual(sr.env("DEFINITELY_NOT_SET_12345"), "")


if __name__ == "__main__":
    unittest.main()
