"""Pushing an agent's work — to a fresh branch, never onto a shared one.

The owner replaced the old rule on 2026-09-19. It used to be "push straight to
dev or staging after a /push approval"; it is now "push to a new branch, open a
PR to dev, and merge only after approving it in Telegram". These tests were
rewritten with that change, so the file that used to assert `validate_target
("dev") is allowed` now asserts the opposite -- deliberately, because allowing
it again would put an agent's commit on dev without a review.

The merge/PR half of the rule lives in tests/test_ghflow.py.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class PushTargetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "worktrees").mkdir(parents=True)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "pushgate", "ghflow"):
            sys.modules.pop(mod, None)
        import pushgate
        self.pg = pushgate

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "pushgate", "ghflow"):
            sys.modules.pop(mod, None)

    def test_dev_and_staging_are_no_longer_push_targets(self):
        # The rule change, pinned: work reaches dev through a reviewed PR only.
        for shared in ("dev", "staging"):
            ok, reason = self.pg.validate_target(shared)
            self.assertFalse(ok, shared)
            self.assertIn("refused", reason)

    def test_main_master_production_prod_are_refused(self):
        for bad in ("main", "master", "production", "prod", "MAIN", "Prod"):
            ok, reason = self.pg.validate_target(bad)
            self.assertFalse(ok, bad)
            self.assertIn("refused", reason)

    def test_an_unnamespaced_branch_is_refused(self):
        ok, reason = self.pg.validate_target("feature/x")
        self.assertFalse(ok)
        self.assertIn("ah/", reason)

    def test_an_empty_target_is_refused(self):
        self.assertFalse(self.pg.validate_target("")[0])

    def test_a_fresh_agent_branch_is_allowed(self):
        self.assertTrue(self.pg.validate_target("ah/task-030-20260919-120000")[0])

    def test_a_task_id_with_a_slash_is_refused(self):
        ok, _ = self.pg.plan("../etc")
        self.assertFalse(ok)

    def test_a_missing_worktree_is_refused(self):
        ok, reason = self.pg.plan("task-999")
        self.assertFalse(ok)
        self.assertIn("worktree", reason.lower())

    def test_a_plan_to_main_is_refused_before_touching_git(self):
        (self.root / "worktrees" / "task-030").mkdir()
        ok, _ = self.pg.plan("task-030", "main")
        self.assertFalse(ok)

    def test_a_plan_to_dev_is_refused_before_touching_git(self):
        (self.root / "worktrees" / "task-030").mkdir()
        ok, reason = self.pg.plan("task-030", "dev")
        self.assertFalse(ok)
        self.assertIn("refused", reason)

    def test_a_plan_without_a_target_mints_a_fresh_branch(self):
        (self.root / "worktrees" / "task-030").mkdir()
        ok, info = self.pg.plan("task-030")
        self.assertTrue(ok, info)
        self.assertTrue(info["branch"].startswith("ah/"))
        self.assertIn("task-030", info["branch"])
        self.assertTrue(str(info["worktree"]).endswith("worktrees/task-030"))

    def test_a_dirty_worktree_is_refused_before_pushing(self):
        # A push sends HEAD, so uncommitted work would vanish from the PR the
        # owner is about to approve.
        (self.root / "worktrees" / "task-031").mkdir()
        self.pg.dirty = lambda _wt: True
        ok, reason = self.pg.plan("task-031")
        self.assertFalse(ok)
        self.assertIn("commit", reason.lower())

    def test_a_clean_worktree_passes(self):
        (self.root / "worktrees" / "task-032").mkdir()
        self.pg.dirty = lambda _wt: False
        ok, info = self.pg.plan("task-032")
        self.assertTrue(ok, info)

    def test_push_without_a_repo_is_refused(self):
        (self.root / "worktrees" / "task-030").mkdir()
        res = self.pg.push("task-030")
        self.assertFalse(res["ok"])
        self.assertIn("repo", res["error"])


if __name__ == "__main__":
    unittest.main()
