""""Running" is not "listening", and the difference cost a day of silence.

2026-09-21: the owner sent two messages to @AskNexAIBot and got no reply, while
the unit was active, the tmux session was up and the Claude Code process had
been alive for 31 hours. The channel plugin's MCP server — the only path an
inbound Telegram message takes — had exited. Nothing noticed, because every
check asked whether the *session* was alive and none asked whether the *bridge*
was connected.

These tests pin the distinction, because it is the whole point of the module.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import channel_health as ch  # noqa: E402

SESSION = ("3042434 claude --channels plugin:telegram@claude-plugins-official "
           "--permission-mode auto --settings /home/ahagent/AI-Workspace/ops/"
           "channels/asknexai-settings.json")
PLUGIN = ("3042436 bun run --cwd /home/ahagent/.claude/plugins/cache/"
          "claude-plugins-official/telegram/0.0.7 --shell=bun --silent start")


class BridgeStatusTests(unittest.TestCase):
    def test_session_plus_plugin_is_healthy(self):
        self.assertEqual(ch.bridge_status([SESSION, PLUGIN]), ch.HEALTHY)

    def test_session_without_plugin_is_deaf(self):
        # The exact failure observed: awake, and unable to hear anything.
        self.assertEqual(ch.bridge_status([SESSION]), ch.DEAF)

    def test_nothing_running_is_down(self):
        self.assertEqual(ch.bridge_status([]), ch.DOWN)

    def test_a_plugin_without_a_session_is_not_healthy(self):
        self.assertEqual(ch.bridge_status([PLUGIN]), ch.DOWN)

    def test_an_unrelated_bun_process_does_not_count_as_the_plugin(self):
        unrelated = "999 bun run --cwd /srv/some-other-app start"
        self.assertEqual(ch.bridge_status([SESSION, unrelated]), ch.DEAF)

    def test_an_unrelated_claude_process_does_not_count_as_the_session(self):
        # `claude -p` harness agents also match "claude"; only a --channels
        # session carries the bridge.
        agent = "888 claude -p --settings ops/harness/claude-settings.json"
        self.assertEqual(ch.bridge_status([agent, PLUGIN]), ch.DOWN)


class RepairPolicyTests(unittest.TestCase):
    def test_a_healthy_bridge_is_never_restarted(self):
        # A watchdog that restarts a working service is worse than no watchdog:
        # it drops the conversation context every time it runs.
        self.assertFalse(ch.needs_restart(ch.HEALTHY))

    def test_a_deaf_or_down_bridge_is_restarted(self):
        self.assertTrue(ch.needs_restart(ch.DEAF))
        self.assertTrue(ch.needs_restart(ch.DOWN))


class MessageTests(unittest.TestCase):
    def test_the_deaf_notice_tells_the_owner_to_resend(self):
        # The messages sent while it was deaf were never delivered, so "wait
        # for green" alone would leave them wondering.
        text = ch.MESSAGES[ch.DEAF]
        self.assertIn("kirim ulang", text.lower())
        self.assertIn("tidak akan pernah sampai", text.lower())

    def test_every_unhealthy_status_has_a_message(self):
        for status in (ch.DEAF, ch.DOWN):
            self.assertIn(status, ch.MESSAGES)


if __name__ == "__main__":
    unittest.main()
