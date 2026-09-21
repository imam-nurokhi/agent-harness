"""An engine refusal must be visible to the operator, not just recorded.

`engine.py` remembers a refusal in `agents/.engine.json`. These tests pin
that `state.engines()` surfaces it — the thing both the Command Center
(`/api/state`) and the Telegram bot (`/status`, `/doctor`) read — without
reimplementing engine.py's own logic.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))

REFUSAL = ("Your organization has disabled Claude subscription access for "
           "Claude Code · Use an Anthropic API key instead, or ask your "
           "admin to enable access")


class EngineSurfaceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        os.environ.pop("AH_ENGINE", None)
        os.environ.pop("AH_ENGINE_ORDER", None)
        for mod in ("state", "engine"):
            sys.modules.pop(mod, None)
        import state
        import engine
        self.state, self.engine = state, engine

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_ENGINE", "AH_ENGINE_ORDER"):
            os.environ.pop(var, None)
        for mod in ("state", "engine"):
            sys.modules.pop(mod, None)

    def test_nothing_refused_surfaces_nothing(self):
        info = self.state.engines()
        self.assertEqual(info["refused"], {})
        self.assertTrue(info["chosen"])

    def test_a_refused_engine_is_surfaced_with_its_reason(self):
        self.engine.mark_blocked("claude", REFUSAL)
        info = self.state.engines()
        self.assertIn("claude", info["refused"])
        self.assertIn("disabled Claude subscription", info["refused"]["claude"]["reason"])
        self.assertIn("at", info["refused"]["claude"])

    def test_clearing_removes_it_from_the_surface(self):
        self.engine.mark_blocked("claude", REFUSAL)
        self.engine.clear("claude")
        self.assertEqual(self.state.engines()["refused"], {})

    def test_the_chosen_engine_skips_a_refused_one(self):
        self.engine.mark_blocked("claude", REFUSAL)
        # `state.engines()` must call the real `engine.pick`, not reimplement
        # it, so this only passes if the two ever agree.
        self.assertEqual(self.state.engines()["chosen"], self.engine.pick())


if __name__ == "__main__":
    unittest.main()
