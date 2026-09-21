"""A job that fails must not be reported as done.

`refresh()` used to mark every vanished process as "done" because it only
checked whether the pid was still alive. A crashed engine then reached Telegram
as a green tick. These tests pin the real exit code to the job's status.
"""
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


def _wait(jobs, jid, timeout=15.0):
    """Block until the job leaves 'running', or give up."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        meta = jobs.refresh(jid)
        if meta and jobs.status(meta) != "running":
            return meta
        time.sleep(0.05)
    raise AssertionError(f"job {jid} never finished")


class JobExitStatusTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        root = Path(self._tmp.name)
        (root / "agents" / "roles").mkdir(parents=True)
        for name in ("_common", "lead"):
            (root / "agents" / "roles" / f"{name}.md").write_text("Read only")
        (root / "AGENTS.md").write_text("rules")

        # A fake engine on PATH, so nothing real is ever launched.
        self.bindir = root / "fakebin"
        self.bindir.mkdir()

        os.environ["AH_WORKSPACE"] = str(root)
        # "engine" must be reloaded too: it freezes STATE from state.WORKSPACE
        # at import time, and a stale module would recreate agents/.engine.lock
        # inside a temp dir an earlier test already cleaned up.
        for mod in ("state", "jobs", "engine"):
            sys.modules.pop(mod, None)
        import state  # noqa: F401
        import jobs
        self.jobs = jobs
        self.root = root
        # `agent_env()` puts ~/.local/bin ahead of the inherited PATH, so
        # prepending to PATH is not enough — the real engine would win.
        jobs.EXTRA_PATHS = [self.bindir, *jobs.EXTRA_PATHS]

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "jobs", "engine"):
            sys.modules.pop(mod, None)

    def _engine(self, name: str, body: str) -> None:
        path = self.bindir / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def test_nonzero_exit_is_failed(self):
        self._engine("claude", 'echo "boom" >&2\nexit 3')
        meta = self.jobs.spawn(role="lead", prompt="anything", engine="claude")
        meta = _wait(self.jobs, meta["id"])
        self.assertEqual(self.jobs.status(meta), "failed")
        self.assertEqual(meta.get("code"), 3)

    def test_zero_exit_is_done(self):
        self._engine("claude", 'echo "## Report"\nexit 0')
        meta = self.jobs.spawn(role="lead", prompt="anything", engine="claude")
        meta = _wait(self.jobs, meta["id"])
        self.assertEqual(self.jobs.status(meta), "done")
        self.assertEqual(meta.get("code"), 0)

    def test_stop_beats_exit_code(self):
        """An operator who stops a run sees 'stopped', not 'failed'."""
        self._engine("claude", "sleep 30")
        meta = self.jobs.spawn(role="lead", prompt="anything", engine="claude")
        time.sleep(0.4)
        self.jobs.stop(meta["id"])
        meta = _wait(self.jobs, meta["id"])
        self.assertEqual(self.jobs.status(meta), "stopped")

    def test_listing_reports_failure(self):
        """The status the UI and Telegram read must agree with the exit code."""
        self._engine("claude", "exit 1")
        jid = self.jobs.spawn(role="lead", prompt="anything", engine="claude")["id"]
        _wait(self.jobs, jid)
        row = next(j for j in self.jobs.listing() if j["id"] == jid)
        self.assertEqual(row["status"], "failed")


if __name__ == "__main__":
    unittest.main()
