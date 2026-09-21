"""The harness must run claude as the account that is actually allowed to.

An interactive session here sets CLAUDE_CONFIG_DIR=~/.claude-work — the
imam.nurokhi@nexoratech.co work account. launchd starts the bot and dash
WITHOUT that variable, so the spawned claude fell back to ~/.claude and the
org-disabled team account, and every run was refused. The harness therefore
has to carry the config dir into the environment it hands the engine, instead
of hoping it was inherited.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class AgentAccountTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        os.environ["AH_WORKSPACE"] = self._tmp.name
        # A config dir that exists, so the default is allowed to select it.
        self.cfg = Path(self._tmp.name) / "claude-work"
        self.cfg.mkdir()
        for var in ("AH_CLAUDE_CONFIG_DIR", "CLAUDE_CONFIG_DIR"):
            os.environ.pop(var, None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)
        import jobs
        self.jobs = jobs

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_CLAUDE_CONFIG_DIR", "CLAUDE_CONFIG_DIR"):
            os.environ.pop(var, None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)

    def test_an_explicit_config_dir_is_passed_to_the_engine(self):
        os.environ["AH_CLAUDE_CONFIG_DIR"] = str(self.cfg)
        self.assertEqual(self.jobs.agent_env()["CLAUDE_CONFIG_DIR"], str(self.cfg))

    def test_an_inherited_config_dir_is_preserved(self):
        """A session that already set it must not be overridden."""
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.cfg)
        self.assertEqual(self.jobs.agent_env()["CLAUDE_CONFIG_DIR"], str(self.cfg))

    def test_a_configured_dir_that_does_not_exist_is_not_forced(self):
        """Pointing the engine at a missing dir would break it, not help it."""
        os.environ["AH_CLAUDE_CONFIG_DIR"] = str(self.cfg / "nope")
        self.assertNotIn("CLAUDE_CONFIG_DIR", self.jobs.agent_env())

    def test_an_explicit_setting_beats_the_inherited_one(self):
        os.environ["CLAUDE_CONFIG_DIR"] = "/inherited/but/wrong"
        os.environ["AH_CLAUDE_CONFIG_DIR"] = str(self.cfg)
        self.assertEqual(self.jobs.agent_env()["CLAUDE_CONFIG_DIR"], str(self.cfg))


if __name__ == "__main__":
    unittest.main()
