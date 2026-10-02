"""Plain text becomes work; only the owner's tap becomes a merge.

Two new surfaces on @AgentNexoraBot, both requested by the owner on
2026-09-19:

  * a message without a slash is a development request (it used to be silently
    dropped at tgbot.py:150), and
  * a merge into dev happens only when the owner taps Approve in Telegram.

The callback tests are the ones that matter. An inline button lives in a chat
message, and a message can be forwarded or tapped by whoever else is in the
chat, so the role must be re-checked at the tap and not merely at the /merge
that produced the button.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class FreeFormChatTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "tgchat"):
            sys.modules.pop(mod, None)
        import tgchat
        self.tgchat = tgchat
        self.dir = self.root / "agents" / "chat"
        self.spawned = []

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "tgchat"):
            sys.modules.pop(mod, None)

    def spawn(self, role, prompt):
        self.spawned.append({"role": role, "prompt": prompt})
        return {"id": "999-abc"}

    def test_plain_message_spawns_a_run(self):
        reply = self.tgchat.handle(7, "kenapa login gagal di staging?",
                                   spawn=lambda **kw: self.spawn(kw["role"], kw["prompt"]),
                                   directory=self.dir)
        self.assertIn("999-abc", reply)
        self.assertEqual(len(self.spawned), 1)
        self.assertEqual(self.spawned[0]["role"], "lead")

    def test_leading_role_word_picks_the_agent(self):
        self.tgchat.handle(7, "backend perbaiki endpoint login",
                           spawn=lambda **kw: self.spawn(kw["role"], kw["prompt"]),
                           directory=self.dir)
        self.assertEqual(self.spawned[0]["role"], "backend")
        self.assertIn("perbaiki endpoint login", self.spawned[0]["prompt"])
        self.assertNotIn("backend perbaiki", self.spawned[0]["prompt"])

    def test_a_word_that_is_not_a_role_stays_in_the_question(self):
        self.tgchat.handle(7, "kenapa backend lambat?",
                           spawn=lambda **kw: self.spawn(kw["role"], kw["prompt"]),
                           directory=self.dir)
        self.assertEqual(self.spawned[0]["role"], "lead")
        self.assertIn("kenapa backend lambat?", self.spawned[0]["prompt"])

    def test_prompt_tells_the_agent_it_may_not_push(self):
        self.tgchat.handle(7, "tambahkan tombol ekspor",
                           spawn=lambda **kw: self.spawn(kw["role"], kw["prompt"]),
                           directory=self.dir)
        prompt = self.spawned[0]["prompt"].lower()
        self.assertIn("tidak boleh push", prompt)
        self.assertIn("/push", prompt)

    def test_follow_up_carries_the_previous_turn(self):
        send = lambda **kw: self.spawn(kw["role"], kw["prompt"])
        self.tgchat.handle(7, "cek error di academy", spawn=send, directory=self.dir)
        self.tgchat.handle(7, "kalau yang tadi gimana?", spawn=send, directory=self.dir)
        self.assertIn("cek error di academy", self.spawned[1]["prompt"])

    def test_history_is_capped(self):
        send = lambda **kw: self.spawn(kw["role"], kw["prompt"])
        for i in range(10):
            self.tgchat.handle(7, f"pesan {i}", spawn=send, directory=self.dir)
        self.assertEqual(len(self.tgchat.history(7, self.dir)), self.tgchat.HISTORY_TURNS)

    def test_chats_do_not_share_history(self):
        send = lambda **kw: self.spawn(kw["role"], kw["prompt"])
        self.tgchat.handle(7, "rahasia chat tujuh", spawn=send, directory=self.dir)
        self.tgchat.handle(8, "halo", spawn=send, directory=self.dir)
        self.assertNotIn("rahasia chat tujuh", self.spawned[1]["prompt"])

    def test_oversize_message_is_refused_without_spawning(self):
        reply = self.tgchat.handle(7, "x" * 5000,
                                   spawn=lambda **kw: self.spawn("", ""),
                                   directory=self.dir)
        self.assertIn("terlalu panjang", reply.lower())
        self.assertEqual(self.spawned, [])

    def test_paused_engine_is_reported_not_swallowed(self):
        def refuse(**_kw):
            raise ValueError("semua engine kena limit")

        reply = self.tgchat.handle(7, "halo", spawn=refuse, directory=self.dir)
        self.assertIn("limit", reply)

    def test_empty_message_does_nothing(self):
        self.assertEqual(self.tgchat.handle(7, "   ",
                                            spawn=lambda **kw: self.spawn("", ""),
                                            directory=self.dir), "")
        self.assertEqual(self.spawned, [])


class MergeButtonTests(unittest.TestCase):
    """handle_callback is the only door to ghflow.merge(). Guard it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "ghflow", "tggh", "tgcore"):
            sys.modules.pop(mod, None)
        import ghflow
        import tggh
        self.ghflow, self.tggh = ghflow, tggh

        self.merges, self.answers, self.sent = [], [], []
        tggh.ghflow.merge = lambda repo, number, *a, **k: (
            self.merges.append((repo, number)) or {"ok": True, "sha": "deadbee"})
        tggh.tgcore.call = lambda method, params=None, **k: (
            self.answers.append((method, params)) or {"ok": True})
        tggh.tgcore.send = lambda chat, text, *a, **k: self.sent.append(text)

        self.owner_cfg = {"allowed": [5], "roles": {"5": "owner"}}
        self.viewer_cfg = {"allowed": [5, 9], "roles": {"5": "owner", "9": "viewer"}}
        self.token = ghflow.stage_approval("NexoraTechTeam/academy", 12, "abc1234", 5)

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "ghflow", "tggh", "tgcore"):
            sys.modules.pop(mod, None)

    def _tap(self, cfg, data, who):
        self.tggh.handle_callback(cfg, {
            "id": "cb1", "data": data, "from": {"id": who},
            "message": {"chat": {"id": 5}},
        })

    def test_owner_tap_merges(self):
        self._tap(self.owner_cfg, self.tggh.CB_APPROVE + self.token, 5)
        self.assertEqual(self.merges, [("NexoraTechTeam/academy", 12)])

    def test_owner_tap_records_the_approval(self):
        self._tap(self.owner_cfg, self.tggh.CB_APPROVE + self.token, 5)
        rec = self.ghflow.read_approval("NexoraTechTeam/academy", 12)
        self.assertEqual(rec["approved_by"], "5")

    def test_non_owner_tap_does_not_merge(self):
        self._tap(self.viewer_cfg, self.tggh.CB_APPROVE + self.token, 9)
        self.assertEqual(self.merges, [])

    def test_unpaired_stranger_tap_does_not_merge(self):
        self._tap(self.owner_cfg, self.tggh.CB_APPROVE + self.token, 4242)
        self.assertEqual(self.merges, [])

    def test_unknown_token_does_not_merge(self):
        self._tap(self.owner_cfg, self.tggh.CB_APPROVE + "deadbeef", 5)
        self.assertEqual(self.merges, [])

    def test_forged_token_shape_does_not_merge(self):
        self._tap(self.owner_cfg, self.tggh.CB_APPROVE + "../../etc/passwd", 5)
        self.assertEqual(self.merges, [])

    def test_cancel_does_not_merge(self):
        self._tap(self.owner_cfg, self.tggh.CB_CANCEL + self.token, 5)
        self.assertEqual(self.merges, [])
        self.assertTrue(any("dibatalkan" in s.lower() for s in self.sent))

    def test_unknown_callback_payload_is_ignored(self):
        self._tap(self.owner_cfg, "something:else", 5)
        self.assertEqual(self.merges, [])


if __name__ == "__main__":
    unittest.main()
