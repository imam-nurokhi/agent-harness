"""The hourly sweep: what it starts, what it refuses to start, and what it says.

`resume.pick` decides which task is eligible; this is the loop that acts on it.
Its contract is narrow on purpose:

  - if every engine is out (paused), start nothing and leave a note the bot
    will announce — resuming into a wall only wastes a quota;
  - never start a second run while one is already live;
  - start exactly one eligible task, through the same job path the dashboard
    uses, so an unattended run is not a weaker path than a watched one;
  - record what it did so the next sweep and the operator can see it.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class ResumeRunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        (self.root / "agents" / "roles").mkdir(parents=True)
        (self.root / "agents" / "claims").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        (self.root / "AGENTS.md").write_text("rules")
        for name in ("_common", "backend", "lead"):
            (self.root / "agents" / "roles" / f"{name}.md").write_text("Read only")
        os.environ["AH_WORKSPACE"] = str(self.root)
        os.environ.pop("AH_ENGINE", None)
        for mod in ("state", "engine", "jobs", "resume", "resumerun"):
            sys.modules.pop(mod, None)
        import engine
        import resumerun
        self.engine = engine
        self.rr = resumerun
        self._started = []
        self._notes = []
        # Inject the side effects so the loop's decisions are tested, not the
        # engine or Telegram.
        self.rr._spawn = lambda task: (self._started.append(task["id"])
                                       or {"id": "job1", "engine": "claude"})
        self.rr._notify = lambda text: self._notes.append(text)

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "engine", "jobs", "resume", "resumerun"):
            sys.modules.pop(mod, None)

    def _task(self, tid, role="backend", done=0, total=2, worktree=True):
        crit = "".join(
            f"- [{'x' if i < done else ' '}] c{i}\n" for i in range(total))
        (self.root / "agents" / "tasks" / f"{tid}.md").write_text(
            f"# Task: {tid}\n\n- **Role:** {role}\n- **Class:** personal\n"
            f"- **Project:** AI-Workspace\n\n## Acceptance criteria\n{crit}\n"
            f"## Report\n")
        if worktree:
            (self.root / "worktrees" / tid).mkdir(exist_ok=True)

    def test_it_starts_one_eligible_task(self):
        self._task("task-030", done=1, total=3)
        self.rr.sweep(live_task_ids=set())
        self.assertEqual(self._started, ["task-030"])

    def test_it_starts_nothing_when_paused(self):
        self._task("task-030", done=1, total=3)
        self.engine.mark("claude", self.engine.KIND_REFUSED, "disabled")
        self.engine.mark("codex", self.engine.KIND_LIMITED, "limit",
                         until=9999999999)
        self.rr.sweep(live_task_ids=set())
        self.assertEqual(self._started, [])
        self.assertTrue(any("paus" in n.lower() for n in self._notes),
                        "a paused sweep must say so")

    def test_it_starts_nothing_when_a_run_is_already_live(self):
        self._task("task-030", done=1, total=3)
        self.rr.sweep(live_task_ids={"task-030"})
        self.assertEqual(self._started, [])

    def test_it_starts_nothing_when_something_else_is_live(self):
        """One agent at a time: a busy harness is not given a second task."""
        self._task("task-030", done=1, total=3)
        self.rr.sweep(live_task_ids={"task-099"})
        self.assertEqual(self._started, [])

    def test_a_clean_board_starts_nothing_and_stays_quiet(self):
        self._task("task-030", done=2, total=2)   # finished
        self.rr.sweep(live_task_ids=set())
        self.assertEqual(self._started, [])
        self.assertEqual(self._notes, [])

    def test_starting_a_task_announces_it(self):
        self._task("task-030", done=1, total=3)
        self.rr.sweep(live_task_ids=set())
        self.assertTrue(any("task-030" in n for n in self._notes))


if __name__ == "__main__":
    unittest.main()
