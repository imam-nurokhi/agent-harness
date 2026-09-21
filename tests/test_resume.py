"""Which stalled task an unattended sweep may pick up, and which it must not.

The owner wants work that stopped half-finished to continue on its own, every
hour, without being asked. The danger in that is obvious: an unattended agent
picking the wrong task, jumping work someone else holds, or touching a task
that was explicitly marked hands-off. This is the guardrail, and it is tested
before it is trusted.

The rules, in one place:
  - a task is a candidate only if it has a worktree and unmet criteria and no
    report yet — work that was genuinely started and genuinely not finished;
  - never a task whose file says do-not-run;
  - never a task another agent is holding, or that has a live run;
  - never a task in a project on hold;
  - one task per sweep, the same one each time until it moves, so the work is
    directed, not scattered.
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class ResumePickTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        (self.root / "agents" / "roles").mkdir(parents=True)
        (self.root / "agents" / "claims").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        (self.root / "AGENTS.md").write_text("Documents off-limits")
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "engine", "resume"):
            sys.modules.pop(mod, None)
        import resume
        self.resume = resume

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "engine", "resume"):
            sys.modules.pop(mod, None)

    def _task(self, tid, role="backend", klass="personal", done=0, total=2,
              worktree=True, body_extra="", project="AI-Workspace"):
        crit = "".join(
            f"- [{'x' if i < done else ' '}] criterion {i}\n" for i in range(total))
        (self.root / "agents" / "tasks" / f"{tid}.md").write_text(
            f"# Task: {tid}\n\n- **Role:** {role}\n- **Class:** {klass}\n"
            f"- **Project:** {project}\n\n"
            f"## Acceptance criteria\n{crit}\n{body_extra}\n## Report\n")
        if worktree:
            (self.root / "worktrees" / tid).mkdir(exist_ok=True)

    def _claim(self, tid):
        (self.root / "agents" / "claims" / f"{tid}.claim").write_text(
            f"task={tid}\nby=someone\n")

    def _pick(self, live_tasks=None):
        return self.resume.pick(live_task_ids=live_tasks or set())

    # --- the happy path -----------------------------------------------------

    def test_a_started_unfinished_task_is_picked(self):
        self._task("task-030", done=1, total=3)
        chosen = self._pick()
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["id"], "task-030")
        self.assertEqual(chosen["role"], "backend")

    def test_nothing_is_picked_when_the_board_is_clean(self):
        self._task("task-030", done=3, total=3)   # finished
        self.assertIsNone(self._pick())

    # --- what makes something ineligible ------------------------------------

    def test_a_planned_task_without_a_worktree_is_left_alone(self):
        """No worktree means nobody has started it; starting it is a human call."""
        self._task("task-031", worktree=False)
        self.assertIsNone(self._pick())

    def test_a_do_not_run_task_is_never_picked(self):
        self._task("task-038", body_extra="> **JANGAN DIJALANKAN DULU.** menunggu owner\n")
        self.assertIsNone(self._pick())

    def test_a_claimed_task_is_left_to_its_holder(self):
        self._task("task-030")
        self._claim("task-030")
        self.assertIsNone(self._pick())

    def test_a_task_with_a_live_run_is_not_double_started(self):
        self._task("task-030")
        self.assertIsNone(self._pick(live_tasks={"task-030"}))

    def test_a_task_in_a_held_project_is_skipped(self):
        """Scope holds are honoured through an injected predicate."""
        self._task("task-050", klass="nexora", project="NEXONE")
        self.assertIsNone(self.resume.pick(
            live_task_ids=set(),
            is_held=lambda t: t.get("klass") == "nexora"))
        # And with nothing held, the same task is eligible again.
        self.assertIsNotNone(self.resume.pick(
            live_task_ids=set(), is_held=lambda t: False))

    def test_a_finished_looking_task_awaiting_review_is_not_reworked(self):
        """All criteria ticked means it is done enough; do not poke it again."""
        self._task("task-030", done=2, total=2)
        self.assertIsNone(self._pick())

    # --- structure: one, and the same one -----------------------------------

    def test_only_one_task_is_returned_even_when_several_qualify(self):
        self._task("task-030", done=1, total=3)
        self._task("task-031", done=1, total=3)
        self._task("task-032", done=1, total=3)
        chosen = self._pick()
        self.assertIsNotNone(chosen)

    def test_the_choice_is_stable_across_sweeps(self):
        """A directed sweep finishes one thing; it must not thrash between tasks."""
        self._task("task-032", done=1, total=3)
        self._task("task-030", done=1, total=3)
        self._task("task-031", done=1, total=3)
        first = self._pick()["id"]
        self.assertEqual(first, self._pick()["id"])
        self.assertEqual(first, self._pick()["id"])

    def test_a_lead_or_docs_task_needs_no_worktree(self):
        """Planning roles legitimately run at the workspace root."""
        self._task("task-040", role="lead", worktree=False, done=0, total=2)
        chosen = self._pick()
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["id"], "task-040")


if __name__ == "__main__":
    unittest.main()
