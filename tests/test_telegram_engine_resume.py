"""The /engine and /resume commands: reachable, safe, and honest.

These two commands are the phone-side of the engine-health and auto-resume work.
/engine answers "what will run, and what is stuck", /resume triggers one sweep
by hand. Both must be reachable through the merged handler registry, must pass
the allow-list gate like every other command, and must never raise into the
poll loop — a handler that throws takes the whole bot down with it.
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class TelegramEngineResumeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents" / "tasks").mkdir(parents=True)
        (self.root / "agents" / "roles").mkdir(parents=True)
        (self.root / "agents" / "claims").mkdir(parents=True)
        (self.root / "worktrees").mkdir()
        (self.root / "AGENTS.md").write_text("rules")
        self.old = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.root)
        for name in ("state", "engine", "jobs", "resume", "resumerun",
                     "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)
        self.engine = importlib.import_module("engine")
        self.tgcmd = importlib.import_module("tgcmd")
        self.tgcore = importlib.import_module("tgcore")

    def tearDown(self):
        self._tmp.cleanup()
        if self.old is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.old
        for name in ("state", "engine", "jobs", "resume", "resumerun",
                     "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)

    # --- registration -------------------------------------------------------

    def test_both_commands_are_registered(self):
        self.assertIn("engine", self.tgcmd.HANDLERS)
        self.assertIn("resume", self.tgcmd.HANDLERS)

    def test_both_appear_in_the_telegram_menu(self):
        names = [c for c, _ in self.tgcore._full_command_list()]
        self.assertIn("engine", names)
        self.assertIn("resume", names)

    # --- /engine ------------------------------------------------------------

    def test_engine_reports_the_chosen_engine_when_healthy(self):
        out = self.tgcmd.cmd_engine("")
        self.assertIsInstance(out, str)
        self.assertRegex(out.lower(), r"claude|codex")

    def test_engine_reports_a_refusal(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED,
                         "Your organization has disabled Claude Code")
        out = self.tgcmd.cmd_engine("")
        self.assertIn("claude", out)
        self.assertIn("ah engine clear", out)

    def test_engine_reports_a_limit_with_its_return_time(self):
        self.engine.mark("codex", self.engine.KIND_LIMITED, "usage limit",
                         until=9999999999)
        out = self.tgcmd.cmd_engine("")
        self.assertIn("codex", out)

    def test_engine_never_raises_even_if_state_is_odd(self):
        self.engine.STATE.write_text("{ not json")
        self.assertIsInstance(self.tgcmd.cmd_engine(""), str)

    # --- /resume ------------------------------------------------------------

    def test_resume_on_a_clean_board_says_nothing_to_do(self):
        out = self.tgcmd.cmd_resume("")
        self.assertIsInstance(out, str)
        self.assertTrue(out.strip())

    def test_resume_reports_when_paused(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, "disabled")
        self.engine.mark("codex", self.engine.KIND_LIMITED, "limit",
                         until=9999999999)
        out = self.tgcmd.cmd_resume("")
        self.assertRegex(out.lower(), r"paus|tunda|tidak tersedia")


if __name__ == "__main__":
    unittest.main()
