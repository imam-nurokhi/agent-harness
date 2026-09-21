"""A task still holding its template placeholders must never be auto-resumed.

Observed 2026-09-21: `@AgentNexoraBot` sent the identical alert every hour for
nine hours —

    ⚠️ Auto-resume gagal — task-018 tidak bisa dimulai:
    unknown role: lead | frontend | backend | qa | review | devops | docs

The message reads like a list of valid roles. It is not: it is the *value* of
the Role field, because `ah task new` writes the menu of options into the field
itself and nothing distinguishes "unfilled template" from "filled in". The task
had a worktree, so the sweep judged it stalled-but-startable, tried to spawn it,
failed on an impossible role, alerted, and did the same thing again an hour
later — forever, because nothing about the failure could change on its own.

Three separate defects, one per layer, and fixing only the task would leave the
trap armed for the next one:

  1. a placeholder is read as a real value (`state._field`);
  2. a task that cannot possibly start is still offered to the sweep (`resume`);
  3. an unfixable failure is re-announced on every tick (`resumerun`).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))

TEMPLATE_ROLE = "lead | frontend | backend | qa | review | devops | docs"
TEMPLATE_CLASS = "cbqa | nexora | freelance | personal | sandbox"


class PlaceholderFieldTests(unittest.TestCase):
    """Layer 1: an unfilled field is not a value."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        sys.modules.pop("state", None)
        import state
        self.state = state

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        sys.modules.pop("state", None)

    def test_the_role_menu_is_not_a_role(self):
        self.assertEqual(self.state._field(f"- **Role:** {TEMPLATE_ROLE}", "Role"), "")

    def test_the_class_menu_is_not_a_class(self):
        self.assertEqual(self.state._field(f"- **Class:** {TEMPLATE_CLASS}", "Class"), "")

    def test_angle_bracket_placeholders_are_not_values(self):
        for raw in ("<name> (`<path>`)", "<develop|main>", "<one sentence>"):
            self.assertEqual(self.state._field(f"- **Project:** {raw}", "Project"), "",
                             f"{raw!r} should read as unset")

    def test_a_real_value_still_survives(self):
        self.assertEqual(self.state._field("- **Role:** backend", "Role"), "backend")
        self.assertEqual(
            self.state._field("- **Project:** academy (`projects/academy`)", "Project"),
            "academy (`projects/academy`)")

    def test_a_real_value_may_contain_a_hyphen_or_slash(self):
        # Guard against over-blocking: these are ordinary, not placeholders.
        self.assertEqual(self.state._field("- **Base branch:** dev", "Base branch"), "dev")
        self.assertEqual(
            self.state._field("- **Project:** NexoraTechTeam/academy", "Project"),
            "NexoraTechTeam/academy")


class UnstartableTaskTests(unittest.TestCase):
    """Layer 2: the sweep must not offer a task that cannot be started."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        (self.root / "agents" / "roles").mkdir(parents=True)
        (self.root / "agents" / "claims").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        (self.root / "AGENTS.md").write_text("rules")
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

    def _task(self, tid, role="backend", worktree=True):
        (self.root / "agents" / "tasks" / f"{tid}.md").write_text(
            f"# Task: {tid}\n\n- **Role:** {role}\n- **Class:** personal\n"
            f"- **Project:** AI-Workspace\n\n"
            f"## Acceptance criteria\n- [ ] satu\n- [ ] dua\n\n## Report\n")
        if worktree:
            (self.root / "worktrees" / tid).mkdir(exist_ok=True)

    def ids(self):
        return [t["id"] for t in self.resume.candidates(is_held=lambda _t: False)]

    def test_a_configured_stalled_task_is_still_picked(self):
        # The guard must not swallow the feature it protects.
        self._task("task-001", role="backend")
        self.assertIn("task-001", self.ids())

    def test_a_task_left_on_the_template_role_is_not_picked(self):
        self._task("task-018", role=TEMPLATE_ROLE)
        self.assertNotIn("task-018", self.ids())

    def test_a_task_with_no_role_at_all_is_not_picked(self):
        self._task("task-019", role="")
        self.assertNotIn("task-019", self.ids())

    def test_a_task_with_a_role_that_does_not_exist_is_not_picked(self):
        # Typos fail exactly like placeholders do, and for the same reason.
        self._task("task-020", role="beckend")
        self.assertNotIn("task-020", self.ids())

    def test_the_unstartable_task_is_reported_as_needing_configuration(self):
        # Silently skipping is its own failure: the owner must be able to find
        # out why nothing is happening.
        self._task("task-018", role=TEMPLATE_ROLE)
        blocked = self.resume.unconfigured()
        self.assertEqual([t["id"] for t in blocked], ["task-018"])
        self.assertIn("role", blocked[0]["reason"].lower())


class RepeatedFailureTests(unittest.TestCase):
    """Layer 3: an identical, unfixable failure is announced once, not hourly."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "engine", "jobs", "resume", "resumerun"):
            sys.modules.pop(mod, None)
        import resumerun
        self.resumerun = resumerun

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "engine", "jobs", "resume", "resumerun"):
            sys.modules.pop(mod, None)

    def test_the_same_failure_is_not_announced_twice(self):
        first = self.resumerun.should_announce("task-018", "unknown role: x")
        second = self.resumerun.should_announce("task-018", "unknown role: x")
        self.assertTrue(first, "the first occurrence must always be announced")
        self.assertFalse(second, "nine identical alerts in nine hours is the bug")

    def test_a_different_failure_on_the_same_task_is_announced(self):
        self.resumerun.should_announce("task-018", "unknown role: x")
        self.assertTrue(self.resumerun.should_announce("task-018", "no worktree"))

    def test_the_same_failure_on_another_task_is_announced(self):
        self.resumerun.should_announce("task-018", "unknown role: x")
        self.assertTrue(self.resumerun.should_announce("task-019", "unknown role: x"))

    def test_a_recovered_task_may_alert_again_later(self):
        self.resumerun.should_announce("task-018", "unknown role: x")
        self.resumerun.clear_failure("task-018")
        self.assertTrue(self.resumerun.should_announce("task-018", "unknown role: x"))


if __name__ == "__main__":
    unittest.main()
