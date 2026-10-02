"""The auto-resume sweep against real state, not injected doubles.

The unit tests inject around `_spawn` and `_live_task_ids`, which is right for
testing the decision logic but hid two real failures: the sweep read every
assigned-but-idle task as a live run and never did anything, and when it did
run, `_spawn` passed a project field that jobs.spawn could not parse and threw.
These tests drive the real functions so neither can come back.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class ResumeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        (self.root / "agents" / "roles").mkdir(parents=True)
        (self.root / "agents" / "claims").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        (self.root / "AGENTS.md").write_text("rules")
        for name in ("_common", "backend", "lead", "devops"):
            (self.root / "agents" / "roles" / f"{name}.md").write_text("Read only")
        self.bindir = self.root / "fakebin"
        self.bindir.mkdir()
        os.environ["AH_WORKSPACE"] = str(self.root)
        os.environ.pop("AH_ENGINE", None)
        for mod in ("state", "engine", "jobs", "resume", "resumerun"):
            sys.modules.pop(mod, None)
        import state  # noqa: F401
        import jobs
        import resumerun
        self.jobs, self.rr = jobs, resumerun
        jobs.EXTRA_PATHS = [self.bindir, *jobs.EXTRA_PATHS]
        (self.bindir / "claude").write_text('#!/bin/sh\necho "## Report"\nexit 0\n')
        (self.bindir / "claude").chmod(0o755)
        self._notes = []
        self.rr._notify = lambda text: self._notes.append(text)

    def _drain_jobs(self, timeout=20.0):
        """Wait for detached job processes before removing the directory.

        jobs.spawn starts the engine with start_new_session=True, so the child
        outlives the test body and keeps writing its log and .rc file. Removing
        the workspace underneath it raced and failed the teardown with
        "OSError: Directory not empty: '.jobs'" on roughly half of all runs,
        which made the whole suite unusable as a gate.
        """
        jobs_dir = self.root / "agents" / ".jobs"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not any(self._unsettled(m) for m in jobs_dir.glob("*.json")):
                return
            time.sleep(0.05)

    @staticmethod
    def _unsettled(meta_path):
        """A job still holding the directory open.

        A spawn that never started writes no .rc at all, so waiting on the file
        alone costs the full timeout. The process being gone settles it too.
        """
        if meta_path.with_suffix(".rc").exists():
            return False
        try:
            pid = json.loads(meta_path.read_text()).get("pid")
        except Exception:
            return False
        if not pid:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def tearDown(self):
        self._drain_jobs()
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "engine", "jobs", "resume", "resumerun"):
            sys.modules.pop(mod, None)

    def _task(self, tid, role="backend", done=1, total=3):
        crit = "".join(
            f"- [{'x' if i < done else ' '}] c{i}\n" for i in range(total))
        (self.root / "agents" / "tasks" / f"{tid}.md").write_text(
            f"# Task: {tid}\n\n- **Role:** {role}\n- **Class:** personal\n"
            f"- **Project:** AI-Workspace (`~/AI-Workspace`)\n\n"
            f"## Acceptance criteria\n{crit}\n## Report\n")
        (self.root / "worktrees" / tid).mkdir(exist_ok=True)

    # --- HIGH #2: assigned-but-idle is not "busy" ---------------------------

    def test_assigned_idle_tasks_do_not_read_as_a_live_run(self):
        """A board with assigned tasks and no running process is not busy."""
        self._task("task-030")
        self._task("task-031", role="devops")
        # No engine process is running. The sweep must not see itself as busy.
        self.assertNotIn("__busy__", self.rr._live_task_ids())

    def test_the_sweep_actually_starts_a_task_on_an_idle_board(self):
        self._task("task-030")
        result = self.rr.sweep()
        self.assertEqual(result.get("action"), "started")
        self.assertEqual(result.get("task"), "task-030")

    # --- HIGH #1: _spawn survives the real project field --------------------

    def test_spawn_does_not_choke_on_the_project_field(self):
        """The Project field reads 'Name (`~/path`)', which is not a path."""
        self._task("task-030")
        task = {"id": "task-030", "role": "backend",
                "project": "AI-Workspace (`~/AI-Workspace`)", "title": "t"}
        meta = self.rr._spawn(task)          # must not raise
        self.assertIn("id", meta)
        # And it lands in the task's worktree, not the workspace root.
        self.assertTrue(meta["cwd"].endswith("worktrees/task-030"))

    def test_a_started_sweep_announces_and_runs_to_completion(self):
        self._task("task-030")
        result = self.rr.sweep()
        self.assertEqual(result["action"], "started")
        self.assertTrue(any("task-030" in n for n in self._notes))
        deadline = time.time() + 15
        while time.time() < deadline:
            meta = self.jobs.refresh(result["job"])
            if self.jobs.status(meta) != "running":
                break
            time.sleep(0.05)
        self.assertEqual(self.jobs.status(meta), "done")


    def test_the_operators_own_session_is_not_seen_as_a_running_job(self):
        """The busy gate must key off harness jobs, not any claude on the box.

        The interactive session that installs the harness is itself a `claude`
        with its cwd in the workspace. Counting it made the sweep permanently
        busy whenever someone had a terminal open.
        """
        self._task("task-030")
        # No harness job has been spawned; jobs.listing() is empty. Even if a
        # stray engine is running elsewhere, the sweep must not read it as busy.
        self.assertNotIn("__busy__", self.rr._live_task_ids())
        self.assertEqual(self.rr.sweep().get("action"), "started")

    def test_a_running_harness_job_does_make_it_busy(self):
        self._task("task-030")
        (self.bindir / "claude").write_text("#!/bin/sh\nsleep 20\n")
        (self.bindir / "claude").chmod(0o755)
        self.jobs.spawn(role="backend", prompt="x", engine="claude")
        self.assertIn("__busy__", self.rr._live_task_ids())


if __name__ == "__main__":
    unittest.main()
