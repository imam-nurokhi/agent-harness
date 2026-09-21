"""The bridge must announce its own death on Telegram.

A chat surface that dies silently looks identical to a chat surface that is
merely thinking, so `/exit` in the tmux pane used to be indistinguishable from
a slow answer. systemd now calls bin/channel_notify.py on start and stop.

The two rules worth testing are the ones that would leak a credential or spam a
stranger if they broke: the token is read from the channel's own .env (never
the workspace .env, which belongs to the other bot), and the recipients are
exactly the channel allowlist.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import channel_notify  # noqa: E402


class ChannelNotifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_reads_token_from_channel_env(self):
        env = self.dir / ".env"
        env.write_text("# comment\nTELEGRAM_BOT_TOKEN=123:abc\n")
        self.assertEqual(channel_notify.read_token(env), "123:abc")

    def test_token_strips_quotes_and_ignores_other_keys(self):
        env = self.dir / ".env"
        env.write_text("OTHER=x\nTELEGRAM_BOT_TOKEN='9:zz'\n")
        self.assertEqual(channel_notify.read_token(env), "9:zz")

    def test_missing_env_is_not_an_error(self):
        self.assertEqual(channel_notify.read_token(self.dir / "nope.env"), "")

    def test_recipients_are_the_channel_allowlist(self):
        access = self.dir / "access.json"
        access.write_text(json.dumps({
            "dmPolicy": "allowlist",
            "allowFrom": ["6687943152", "6687943152", 42],
        }))
        self.assertEqual(channel_notify.read_recipients(access), ["6687943152", "42"])

    def test_no_allowlist_means_no_recipients(self):
        access = self.dir / "access.json"
        access.write_text(json.dumps({"dmPolicy": "pairing"}))
        self.assertEqual(channel_notify.read_recipients(access), [])

    def test_corrupt_access_file_is_not_an_error(self):
        access = self.dir / "access.json"
        access.write_text("{not json")
        self.assertEqual(channel_notify.read_recipients(access), [])

    def test_unknown_event_exits_zero_without_sending(self):
        sent = []
        original = channel_notify.send
        channel_notify.send = lambda *a: sent.append(a) or True
        self.addCleanup(lambda: setattr(channel_notify, "send", original))
        self.assertEqual(channel_notify.main(["channel_notify.py", "sideways"]), 0)
        self.assertEqual(sent, [])

    def test_down_message_names_the_exit_case(self):
        self.assertIn("/exit", channel_notify.MESSAGES["down"])
        self.assertIn("Restart=always", channel_notify.MESSAGES["down"])


if __name__ == "__main__":
    unittest.main()
