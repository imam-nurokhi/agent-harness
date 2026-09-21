"""Trigger integration tests use an isolated workspace and fake engine."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TriggerTests(unittest.TestCase):
    def test_fanout_and_legacy(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            roles = root / "agents/roles"
            roles.mkdir(parents=True)
            for name in ("_common", "devops", "lead"):
                (roles / (name + ".md")).write_text("Read only")
            (root / "agents/.scope").write_text("HOLD cbqa/*\nHOLD nexora/NEXFINANCE\n")
            for name in ("SUPPORT", "NEXONE", "NEXFINANCE"):
                target = root / "real" / name
                target.mkdir(parents=True)
                link = root / "projects/nexora" / name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(target, target_is_directory=True)
            (root / "projects/cbqa/held").mkdir(parents=True)
            config = root / "agents/triggers.json"
            config.write_text(json.dumps({"triggers": [
                {"id": "health", "role": "devops", "per_project": True, "prompt": "{PROJECTS}"},
                {"id": "standup", "role": "lead", "prompt": "tasks"}]}))
            script = 'source "$1/bin/lib/common.sh"; LIB="$1/bin/lib"; source "$LIB/trigger.sh"; claude() { printf "ENGINE cwd=%s\\n" "$(pwd -P)"; printf "%s\\n" "$@"; }; trg_run "$2"'
            env = {**os.environ, "AH_WORKSPACE": str(root)}
            for trigger, count in (("health", 2), ("standup", 1)):
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", script, "test", str(ROOT), trigger], env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                logs = list((root / "agents/reports").glob(f"trigger-{trigger}.*.log"))
                self.assertEqual(len(logs), 1)
                content = logs[0].read_text()
                self.assertEqual(content.count("ENGINE cwd="), count, content)
                self.assertNotIn("NEXFINANCE", content)
                self.assertNotIn("cbqa", content)
                if trigger == "health":
                    for name in ("SUPPORT", "NEXONE"):
                        self.assertIn(f"ENGINE cwd={root}/real/{name}", content)
                else:
                    self.assertIn(f"ENGINE cwd={root}", content)

            failing = script.replace('printf "ENGINE cwd=', 'return 7; printf "ENGINE cwd=')
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", failing, "test", str(ROOT), "health"], env=env, text=True, capture_output=True)
            self.assertEqual(1, result.returncode)
            self.assertEqual(2, result.stdout.count("exit=7"))
            (root / "agents/.scope").write_text("HOLD */*\n")
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script, "test", str(ROOT), "health"], env=env, text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("no agents launched", result.stdout)
            self.assertNotIn("ENGINE cwd=", result.stdout)

    def test_workable_filters_before_metadata(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location("trigger_state", ROOT / "bin/lib/state.py")
        state = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(state)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            for path in ("cbqa/held", "nexora/NEXFINANCE", "nexora/SUPPORT"):
                (root / path).mkdir(parents=True)
            scope = root / "scope"
            scope.write_text("HOLD cbqa/*\nHOLD nexora/NEXFINANCE\n")
            with patch.object(state, "PROJECTS", root), patch.object(state, "SCOPE", scope), patch.object(state, "_describe_project", return_value={}) as describe:
                self.assertEqual([{}], state.workable_projects())
                describe.assert_called_once_with(root / "nexora/SUPPORT", "nexora")

if __name__ == "__main__":
    unittest.main()
