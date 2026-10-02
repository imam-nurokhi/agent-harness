"""/help must show every command the bot will actually accept.

Six working commands -- /diff, /report, /log, /push, /engine, /resume -- were
dispatchable and listed in the Telegram slash-menu but absent from /help, so
the only in-chat reference disagreed with the bot's real surface. These tests
tie the three lists together so they cannot drift apart again.
"""
from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "bin" / "lib"
sys.path.insert(0, str(LIB))

# Not user-facing surface: /start is an alias of /help, /board of /kanban, and
# /pair is the enrolment handshake handled before dispatch.
ALIASES = {"start", "board", "pair"}


class HelpCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        workspace = Path(self.tmp.name)
        for subdir in ("tasks", "reports", "roles", "claims"):
            (workspace / "agents" / subdir).mkdir(parents=True)
        (workspace / "worktrees").mkdir()
        (workspace / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(workspace)
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)
        self.tgcore = importlib.import_module("tgcore")
        self.tgcmd = importlib.import_module("tgcmd")
        self.tgtask = importlib.import_module("tgtask")
        self.tgwatch = importlib.import_module("tgwatch")
        self.tgbot = importlib.import_module("tgbot")
        self.help = self.tgcmd.cmd_help("")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()

    def dispatchable(self) -> set[str]:
        return (set(self.tgcmd.HANDLERS) | set(self.tgtask.HANDLERS)
                | set(self.tgwatch.HANDLERS) | {"grant"}) - ALIASES

    def mentioned(self) -> set[str]:
        # Anchored at line start: /help lists one command per line, and prose
        # like "matikan/nyalakan" or "projects/sandbox" is not a command.
        return set(re.findall(r"(?m)^/([a-z]+)", self.help))

    def test_every_dispatchable_command_appears_in_help(self):
        missing = sorted(self.dispatchable() - self.mentioned())
        self.assertEqual([], missing, f"/help does not mention: {missing}")

    def test_help_does_not_advertise_commands_that_do_not_exist(self):
        # An invented command is worse than a missing one: it fails in the chat.
        extra = sorted(self.mentioned() - self.dispatchable() - ALIASES)
        self.assertEqual([], extra, f"/help advertises non-existent: {extra}")

    def test_slash_menu_and_help_describe_the_same_surface(self):
        menu = {name for name, _ in self.tgcore._full_command_list()} - ALIASES
        self.assertEqual(sorted(menu), sorted(self.dispatchable()))

    def test_every_command_has_a_declared_permission_level(self):
        undeclared = sorted(self.dispatchable() - set(self.tgbot.COMMAND_LEVELS))
        self.assertEqual([], undeclared,
                         f"no COMMAND_LEVELS entry, so they silently require owner: {undeclared}")

    def test_help_marks_which_commands_need_which_role(self):
        # A viewer should be able to tell from /help alone why /run is refused,
        # instead of discovering it by being denied.
        for marker in ("viewer", "operator", "owner"):
            self.assertIn(marker, self.help.lower())

    def test_owner_only_commands_are_shown_as_owner_only(self):
        owner_section = self.help.lower().split("<b>owner</b>", 1)[-1]
        for cmd in ("/run", "/stop", "/push", "/resume", "/doctor", "/grant"):
            self.assertIn(cmd, owner_section, f"{cmd} is owner-only but not shown under owner")


if __name__ == "__main__":
    unittest.main()


class RoleBannerTests(unittest.TestCase):
    """/help points at /status for "what role am I?", so that must be true."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        workspace = Path(self.tmp.name)
        for subdir in ("tasks", "reports", "roles", "claims"):
            (workspace / "agents" / subdir).mkdir(parents=True)
        (workspace / "worktrees").mkdir()
        (workspace / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(workspace)
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)
        self.tgcore = importlib.import_module("tgcore")
        self.tgbot = importlib.import_module("tgbot")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()

    def test_banner_names_the_role_of_the_asking_chat(self):
        cfg = {"allowed": [77], "roles": {"77": "operator"}}
        banner = self.tgbot._role_banner(cfg, 77)
        self.assertIn("operator", banner.lower())

    def test_banner_tells_an_operator_what_is_still_out_of_reach(self):
        cfg = {"allowed": [77], "roles": {"77": "operator"}}
        banner = self.tgbot._role_banner(cfg, 77)
        self.assertIn("owner", banner.lower())

    def test_owner_banner_does_not_nag_about_missing_access(self):
        cfg = {"allowed": [1], "roles": {"1": "owner"}}
        banner = self.tgbot._role_banner(cfg, 1)
        self.assertIn("owner", banner.lower())
        self.assertNotIn("memerlukan", banner.lower())

    def test_help_and_status_both_carry_the_banner(self):
        self.assertIn("status", self.tgbot.ROLE_BANNER_COMMANDS)
        self.assertIn("help", self.tgbot.ROLE_BANNER_COMMANDS)
