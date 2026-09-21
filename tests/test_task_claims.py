"""Ownership for tasks and worktrees.

Two agents sharing this harness will otherwise pick the same task id, or start
work inside a worktree someone else is already using. Claims make ownership
explicit and make the collision loud instead of silent.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "bin" / "lib"
ROOT = LIB.parents[1]
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

PRELUDE = ('source "$1/bin/lib/common.sh"; LIB="$1/bin/lib"; '
           'source "$LIB/claim.sh"; source "$LIB/task.sh"; source "$LIB/wt.sh"; ')


class ClaimTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        (self.root / "agents" / "reports").mkdir(parents=True)
        (self.root / "agents" / "task-templates").mkdir(parents=True)
        (self.root / "agents" / "task-templates" / "task.md").write_text(
            "# Task: <TITLE>\n\n- **ID:** <task-000>\n- **Role:** backend\n\n"
            "## Acceptance criteria\n- [ ] something\n")
        self.task("task-101")

    def tearDown(self):
        self.tmp.cleanup()

    def task(self, task_id: str) -> Path:
        path = self.root / "agents" / "tasks" / f"{task_id}.md"
        path.write_text(f"# Task: Fixture\n\n- **ID:** {task_id}\n- **Role:** backend\n")
        return path

    def sh(self, body: str, owner: str = "alice@box", **env) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "-uo", "pipefail", "-c", PRELUDE + body, "test", str(ROOT)],
            env={**os.environ, "AH_WORKSPACE": str(self.root), "AH_OWNER": owner, **env},
            text=True, capture_output=True,
        )


class ClaimLifecycleTests(ClaimTestCase):
    def test_claim_records_the_owner(self):
        result = self.sh('task_claim task-101 "audit"')
        self.assertEqual(0, result.returncode, result.stderr)
        claim = (self.root / "agents" / "claims" / "task-101.claim").read_text()
        self.assertIn("owner=alice@box", claim)
        self.assertIn("note=audit", claim)

    def test_a_second_owner_is_refused(self):
        self.sh('task_claim task-101 "mine"')
        result = self.sh('task_claim task-101 "also mine"', owner="bob@box")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("alice@box", result.stderr)

    def test_reclaiming_your_own_task_is_not_an_error(self):
        self.sh('task_claim task-101 "first"')
        self.assertEqual(0, self.sh('task_claim task-101 "second"').returncode)

    def test_release_frees_the_task_for_someone_else(self):
        self.sh('task_claim task-101 "mine"')
        self.assertEqual(0, self.sh("task_release task-101").returncode)
        self.assertEqual(0, self.sh('task_claim task-101 "now mine"', owner="bob@box").returncode)

    def test_you_cannot_quietly_release_someone_elses_claim(self):
        self.sh('task_claim task-101 "mine"')
        result = self.sh("task_release task-101", owner="bob@box")
        self.assertNotEqual(0, result.returncode)
        self.assertTrue((self.root / "agents" / "claims" / "task-101.claim").exists())

    def test_a_claim_bound_to_a_dead_process_is_stale_and_can_be_taken_over(self):
        self.sh('claim_bind task-101 "run/backend" 999999')
        result = self.sh('task_claim task-101 "taking over"', owner="bob@box")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("owner=bob@box",
                      (self.root / "agents" / "claims" / "task-101.claim").read_text())

    def test_a_claim_bound_to_a_live_process_holds(self):
        self.sh(f'claim_bind task-101 "run/backend" {os.getpid()}')
        result = self.sh('task_claim task-101 "steal"', owner="bob@box")
        self.assertNotEqual(0, result.returncode)

    def test_manual_claims_do_not_expire_on_their_own(self):
        """No pid means a human holds it; only an explicit release frees it."""
        self.sh('task_claim task-101 "holding this"')
        result = self.sh('task_claim task-101 "steal"', owner="bob@box")
        self.assertNotEqual(0, result.returncode)


class ClaimEnforcementTests(ClaimTestCase):
    def test_worktree_creation_is_blocked_by_a_foreign_claim(self):
        repo = self.root / "repo"
        repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"], ["commit", "-q", "--allow-empty", "-m", "x"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True,
                           capture_output=True)
        self.sh('task_claim task-101 "mine"')
        result = self.sh(f'wt_add task-101 "{repo}"', owner="bob@box")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("alice@box", result.stderr)
        self.assertFalse((self.root / "worktrees" / "task-101").exists())

    def test_task_list_shows_who_holds_what(self):
        self.sh('task_claim task-101 "mine"')
        result = self.sh("task_list", owner="bob@box")
        self.assertIn("alice@box", result.stdout)


class TaskIdAllocationTests(ClaimTestCase):
    def test_concurrent_creation_never_hands_out_the_same_id(self):
        """The real collision: two agents run `ah task new` at the same moment."""
        procs = [
            subprocess.Popen(
                ["bash", "-uo", "pipefail", "-c",
                 PRELUDE + f'task_new "concurrent {i}"', "test", str(ROOT)],
                env={**os.environ, "AH_WORKSPACE": str(self.root), "AH_OWNER": f"a{i}@box"},
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for i in range(8)
        ]
        for p in procs:
            out, err = p.communicate(timeout=60)
            self.assertEqual(0, p.returncode, err)

        created = sorted(p.stem for p in (self.root / "agents" / "tasks").glob("task-*.md"))
        self.assertEqual(9, len(created))  # 8 new + the fixture
        titles = set()
        for path in (self.root / "agents" / "tasks").glob("task-*.md"):
            titles.add(path.read_text().splitlines()[0])
        self.assertEqual(9, len(titles), "a task file was overwritten by a racing writer")


if __name__ == "__main__":
    unittest.main()
