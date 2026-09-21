"""The headless agent's permission surface is an artefact, not a bypass.

The harness runs agents with `claude -p`, which has no interactive approver.
Before this file existed there was no permission policy at all, so every tool
call was refused with "This command requires approval" and the agent burned a
run to report that it was blocked -- see job 135157-520a on 2026-09-17, which
could not even execute `print('hello')`.

The fix is a narrow, reviewable allowlist. These tests exist to stop it
quietly widening into a bypass, because this VPS is shared with dev-kemenkes,
dev-support and monitoring.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "claude-settings.json"
WORKSPACE = "/home/ahagent/AI-Workspace"


class SettingsShapeTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.permissions = self.settings.get("permissions", {})
        self.allow = self.permissions.get("allow", [])
        self.deny = self.permissions.get("deny", [])

    def test_the_file_is_valid_json_with_a_permissions_block(self):
        self.assertIn("permissions", self.settings)
        self.assertTrue(self.allow, "an empty allowlist reproduces the original bug")

    def test_it_never_turns_into_a_blanket_bypass(self):
        self.assertNotEqual("bypassPermissions", self.permissions.get("defaultMode"))
        for rule in self.allow:
            self.assertNotEqual("Bash", rule, "bare Bash allows every command")
            self.assertNotIn("Bash(*)", rule)
            self.assertNotIn("Bash(:*)", rule)

    def test_writes_outside_the_workspace_are_denied(self):
        joined = " ".join(self.deny)
        for path in ("Edit(/etc/", "Edit(/home/ahagent/.ssh", "Edit(/etc/nginx"):
            self.assertIn(path, joined, f"nothing denies writes to {path}")

    def test_credential_files_are_denied_to_the_agent(self):
        joined = " ".join(self.deny)
        # The harness .env holds the Telegram bot token and the Claude OAuth
        # token; an agent summarising tasks has no reason to read it.
        self.assertIn(".env", joined)

    def test_file_denies_use_edit_not_write(self):
        # The CLI warns on every run otherwise: "Write(...) is not matched by
        # file permission checks -- only Edit(path) rules are."
        for rule in self.deny:
            self.assertFalse(rule.startswith("Write("),
                             f"{rule} is dead configuration; use Edit(...)")

    def test_destructive_and_remote_commands_are_denied(self):
        joined = " ".join(self.deny)
        for fragment in ("rm -rf", "sudo", "curl", "ssh"):
            self.assertIn(fragment, joined, f"{fragment} is not denied")

    def test_the_agent_can_read_and_search_the_workspace(self):
        joined = " ".join(self.allow)
        for tool in ("Read", "Grep", "Glob"):
            self.assertIn(tool, joined, f"{tool} is needed to review tasks")

    def test_every_bash_allow_rule_is_scoped_to_a_command(self):
        for rule in self.allow:
            if rule.startswith("Bash("):
                self.assertTrue(rule.endswith(")"), f"malformed rule: {rule}")
                inner = rule[len("Bash("):-1]
                self.assertTrue(inner.strip(), f"empty Bash scope: {rule}")


class InvocationTests(unittest.TestCase):
    """Every path that starts a headless agent must hand over the settings file.

    There are two, and fixing only one is why the first attempt still failed:
    common.sh drives `ah run`, but jobs.py builds its own argv and is the path
    the dashboard and the Telegram /run and /ask commands actually use.
    """

    def setUp(self):
        lib = ROOT.parents[1] / "bin" / "lib"
        self.common = (lib / "common.sh").read_text(encoding="utf-8")
        self.jobs = (lib / "jobs.py").read_text(encoding="utf-8")

    def test_the_shell_path_passes_the_settings_file(self):
        self.assertIn("--settings", self.common)
        self.assertIn("ops/harness/claude-settings.json", self.common)

    def test_the_dashboard_and_telegram_path_passes_the_settings_file(self):
        self.assertIn("--settings", self.jobs)

    def test_neither_path_skips_permissions(self):
        for name, text in (("common.sh", self.common), ("jobs.py", self.jobs)):
            self.assertNotIn("--dangerously-skip-permissions", text, name)
            self.assertNotIn("bypassPermissions", text, name)


if __name__ == "__main__":
    unittest.main()
