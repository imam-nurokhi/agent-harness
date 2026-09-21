"""Telegram must surface engine health the moment it changes, and only then.

The harness can go silently stuck: `claude` refused, `codex` limited, both at
once meaning `engine.paused()` — no job can start. The owner asked, verbatim,
to always be told when that happens. These tests pin the announcement
behaviour in `tgwatch._engine_events`: one message per state change, a
heartbeat (not a flood) while paused, and silence when nothing changed.
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


def _fake_engine_module(unavailable=None, paused=False):
    mod = types.ModuleType("engine")
    mod.KIND_REFUSED = "refused"
    mod.KIND_LIMITED = "limited"
    data = unavailable or {}
    mod.unavailable = lambda: dict(data)
    mod.paused = lambda: paused
    return mod


class EngineNotifyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        for mod in ("state", "jobs", "trigmem", "tgcore", "tgwatch", "engine"):
            sys.modules.pop(mod, None)
        import tgwatch
        self.tgwatch = tgwatch

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AH_WORKSPACE", None)
        for mod in ("state", "jobs", "trigmem", "tgcore", "tgwatch", "engine"):
            sys.modules.pop(mod, None)

    def _set_engine(self, unavailable=None, paused=False):
        sys.modules["engine"] = _fake_engine_module(unavailable, paused)

    def test_nothing_unavailable_announces_nothing(self):
        self._set_engine(unavailable={}, paused=False)
        w = {"primed": True, "engines": {}, "paused": {"active": False, "last_announced": 0}}
        self.assertEqual(self.tgwatch._engine_events(w), [])

    def test_going_unavailable_announces_once_not_twice(self):
        info = {"kind": "refused", "reason": "org disabled it", "at": 1.0, "until": None}
        w = {"primed": True, "engines": {}, "paused": {"active": False, "last_announced": 0}}

        self._set_engine(unavailable={}, paused=False)
        self.assertEqual(self.tgwatch._engine_events(w), [])

        self._set_engine(unavailable={"claude": info}, paused=False)
        first = self.tgwatch._engine_events(w)
        self.assertEqual(len(first), 1)
        self.assertIn("claude", first[0])

        second = self.tgwatch._engine_events(w)
        self.assertEqual(second, [])

    def test_recovery_announces(self):
        info = {"kind": "limited", "reason": "usage limit", "at": 1.0, "until": 9999999999.0}
        w = {"primed": True, "engines": {}, "paused": {"active": False, "last_announced": 0}}

        self._set_engine(unavailable={"codex": info}, paused=False)
        self.tgwatch._engine_events(w)

        self._set_engine(unavailable={}, paused=False)
        events = self.tgwatch._engine_events(w)
        self.assertEqual(len(events), 1)
        self.assertIn("codex", events[0])
        self.assertIn("kembali", events[0].lower())

    def test_entering_paused_announces(self):
        info = {"kind": "refused", "reason": "org disabled it", "at": 1.0, "until": None}
        w = {"primed": True, "engines": {}, "paused": {"active": False, "last_announced": 0}}

        self._set_engine(unavailable={"claude": info, "codex": info}, paused=True)
        events = self.tgwatch._engine_events(w)
        self.assertTrue(any("PAUSED" in e for e in events))

    def test_paused_does_not_repeat_before_heartbeat_but_does_after(self):
        info = {"kind": "refused", "reason": "org disabled it", "at": 1.0, "until": None}
        w = {"primed": True, "engines": {}, "paused": {"active": False, "last_announced": 0}}

        self._set_engine(unavailable={"claude": info}, paused=True)
        events = self.tgwatch._engine_events(w)
        self.assertTrue(any("PAUSED" in e for e in events))

        # Still paused, well within the heartbeat window: no repeat.
        events = self.tgwatch._engine_events(w)
        self.assertFalse(any("PAUSED" in e for e in events))

        # Simulate the heartbeat window having elapsed.
        w["paused"]["last_announced"] -= self.tgwatch.PAUSE_HEARTBEAT_SECONDS + 1
        events = self.tgwatch._engine_events(w)
        self.assertTrue(any("PAUSED" in e for e in events))

    def test_prime_on_fresh_watch_announces_nothing(self):
        info = {"kind": "refused", "reason": "org disabled it", "at": 1.0, "until": None}
        self._set_engine(unavailable={"claude": info}, paused=True)
        w = {"jobs": {}, "tasks": {}, "quiet": False, "primed": False}
        self.tgwatch.prime(w)
        self.assertTrue(w["primed"])
        # A second detect() call right after priming must not surprise-announce
        # the state that prime() already baselined.
        events = self.tgwatch._engine_events(w)
        self.assertEqual(events, [])

    def test_missing_engine_module_degrades_quietly(self):
        # `sys.modules[name] = None` is the standard way to force `import engine`
        # to raise ImportError even though the real module is on disk.
        sys.modules["engine"] = None
        w = {"primed": True, "engines": {}, "paused": {"active": False, "last_announced": 0}}
        self.assertEqual(self.tgwatch._engine_events(w), [])


if __name__ == "__main__":
    unittest.main()
