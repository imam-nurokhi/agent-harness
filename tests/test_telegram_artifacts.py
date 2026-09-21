"""Sending diffs, reports, and logs to Telegram — and refusing to leak secrets.

The value is being able to audit an agent's work from a phone: `/diff` shows
exactly what changed, `/report` the Report block, `/log` the full transcript.
The danger is that the same channel could hand out `.env` or a private key. The
guard is the point of this module and it is tested before it is trusted: a path
outside the workspace, a secret-looking file, or an oversize file is refused,
and the refusal is proven, not assumed.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class ArtifactGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "reports").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "tgfiles"):
            sys.modules.pop(mod, None)
        import tgfiles
        self.tgfiles = tgfiles

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "tgfiles"):
            sys.modules.pop(mod, None)

    def _mk(self, rel, content="data", size=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if size is not None:
            p.write_bytes(b"x" * size)
        else:
            p.write_text(content)
        return p

    def _ok(self, path):
        ok, _ = self.tgfiles.check_sendable(path)
        return ok

    # --- allowed ------------------------------------------------------------

    def test_a_report_inside_the_workspace_is_sendable(self):
        p = self._mk("agents/reports/task-030.md", "report")
        self.assertTrue(self._ok(p))

    def test_a_diff_temp_file_in_the_scratch_area_is_sendable(self):
        p = self._mk("agents/reports/.diff-task-030.patch", "diff")
        self.assertTrue(self._ok(p))

    # --- refused: secrets ---------------------------------------------------

    def test_dotenv_is_refused(self):
        p = self._mk(".env", "TELEGRAM_BOT_TOKEN=secret")
        ok, reason = self.tgfiles.check_sendable(p)
        self.assertFalse(ok)
        self.assertIn("secret", reason.lower())

    def test_a_pem_key_is_refused(self):
        self.assertFalse(self._ok(self._mk("worktrees/x/server.pem")))

    def test_a_private_key_is_refused(self):
        self.assertFalse(self._ok(self._mk("worktrees/x/id_rsa.key")))

    def test_a_p12_bundle_is_refused(self):
        self.assertFalse(self._ok(self._mk("worktrees/x/cert.p12")))

    def test_a_dotenv_with_a_suffix_is_refused(self):
        self.assertFalse(self._ok(self._mk("worktrees/x/.env.production")))

    # --- refused: path traversal -------------------------------------------

    def test_a_path_outside_the_workspace_is_refused(self):
        outside = Path(tempfile.gettempdir()) / "not-in-workspace.txt"
        outside.write_text("x")
        try:
            ok, reason = self.tgfiles.check_sendable(outside)
            self.assertFalse(ok)
            self.assertIn("workspace", reason.lower())
        finally:
            outside.unlink(missing_ok=True)

    def test_a_symlink_escaping_the_workspace_is_refused(self):
        secret = Path(tempfile.gettempdir()) / "escape-secret.txt"
        secret.write_text("x")
        link = self.root / "agents" / "reports" / "innocent.txt"
        try:
            link.symlink_to(secret)
            self.assertFalse(self._ok(link))
        finally:
            link.unlink(missing_ok=True)
            secret.unlink(missing_ok=True)

    # --- refused: size and existence ---------------------------------------

    def test_an_oversize_file_is_refused_clearly(self):
        p = self._mk("agents/reports/big.log", size=self.tgfiles.MAX_BYTES + 1)
        ok, reason = self.tgfiles.check_sendable(p)
        self.assertFalse(ok)
        self.assertIn("20", reason)

    def test_a_file_at_the_limit_is_allowed(self):
        p = self._mk("agents/reports/edge.log", size=self.tgfiles.MAX_BYTES)
        self.assertTrue(self._ok(p))

    def test_a_missing_file_is_refused(self):
        self.assertFalse(self._ok(self.root / "agents/reports/nope.md"))


class ArtifactResolveTests(unittest.TestCase):
    """Which file each command resolves to, without sending anything."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "reports").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "tgfiles"):
            sys.modules.pop(mod, None)
        import tgfiles
        self.tgfiles = tgfiles

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "tgfiles"):
            sys.modules.pop(mod, None)

    def test_report_prefers_the_report_file_then_a_transcript(self):
        (self.root / "agents/reports/task-030.md").write_text("the report")
        got = self.tgfiles.report_path("task-030")
        self.assertTrue(str(got).endswith("task-030.md"))

    def test_report_falls_back_to_a_transcript_log(self):
        (self.root / "agents/reports/task-030.backend.log").write_text("run")
        got = self.tgfiles.report_path("task-030")
        self.assertTrue(str(got).endswith(".log"))

    def test_report_is_none_when_nothing_exists(self):
        self.assertIsNone(self.tgfiles.report_path("task-999"))

    def test_a_task_id_with_a_slash_is_rejected(self):
        """No path components in an id — that is how traversal would sneak in."""
        self.assertIsNone(self.tgfiles.report_path("../../etc/passwd"))


if __name__ == "__main__":
    unittest.main()
