"""Cross-run memory for scheduled triggers.

A trigger that starts blind re-derives the same state every morning. These tests
pin the contract: a run records what it learned, and the next run is handed that
record before it starts.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "bin" / "lib"
ROOT = LIB.parents[1]
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


class TriggerMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.tmp.name)
        (self.workspace / "agents" / "reports").mkdir(parents=True)
        self.old = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.workspace)
        sys.modules.pop("trigmem", None)
        self.trigmem = importlib.import_module("trigmem")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.old
        self.tmp.cleanup()

    def log(self, name: str, body: str) -> Path:
        path = self.workspace / "agents" / "reports" / name
        path.write_text(body)
        return path

    def test_recall_is_empty_before_any_run(self):
        self.assertEqual("", self.trigmem.recall("health"))

    def test_memo_line_is_what_gets_remembered(self):
        log = self.log("t.log", "table\nnoise\nMEMO: SUPPORT test suite still red\ntrailer\n")
        self.trigmem.record("health", 0, str(log))
        self.assertIn("SUPPORT test suite still red", self.trigmem.recall("health"))

    def test_falls_back_to_last_line_when_agent_writes_no_memo(self):
        log = self.log("t.log", "first\n\nlast meaningful line\n\n")
        self.trigmem.record("health", 0, str(log))
        self.assertIn("last meaningful line", self.trigmem.recall("health"))

    def test_failure_status_is_recorded_with_the_entry(self):
        log = self.log("t.log", "MEMO: exploded\n")
        entry = self.trigmem.record("health", 7, str(log))
        self.assertEqual(7, entry["status"])
        self.assertEqual(7, self.trigmem.latest("health")["status"])

    def test_memory_stays_bounded(self):
        log = self.log("t.log", "MEMO: entry\n")
        for _ in range(self.trigmem.KEEP + 4):
            self.trigmem.record("health", 0, str(log))
        stored = json.loads((self.workspace / "agents" / "memory" / "trigger-runs.json").read_text())
        self.assertEqual(self.trigmem.KEEP, len(stored["health"]))

    def test_memo_is_truncated_so_one_run_cannot_flood_the_next_prompt(self):
        log = self.log("t.log", "MEMO: " + ("x" * 5000) + "\n")
        entry = self.trigmem.record("health", 0, str(log))
        self.assertLessEqual(len(entry["memo"]), self.trigmem.MEMO_CHARS)

    def test_triggers_are_remembered_separately(self):
        self.trigmem.record("health", 0, str(self.log("h.log", "MEMO: health said this\n")))
        self.trigmem.record("drift", 0, str(self.log("d.log", "MEMO: drift said that\n")))
        self.assertIn("health said this", self.trigmem.recall("health"))
        self.assertNotIn("drift said that", self.trigmem.recall("health"))


class TriggerRunIntegrationTests(unittest.TestCase):
    """The bash side: a run must both consume and produce memory."""

    SCRIPT = (
        'source "$1/bin/lib/common.sh"; LIB="$1/bin/lib"; source "$LIB/trigger.sh"; '
        'claude() { printf "%s\\n" "$@"; printf "MEMO: run %s finished\\n" "$AH_FAKE_RUN"; }; '
        'trg_run "$2"'
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.tmp.name)
        roles = self.root / "agents" / "roles"
        roles.mkdir(parents=True)
        for name in ("_common", "lead"):
            (roles / f"{name}.md").write_text("Read only")
        (self.root / "agents" / "triggers.json").write_text(json.dumps({
            "triggers": [{"id": "standup", "role": "lead", "prompt": "review the board"}]
        }))

    def tearDown(self):
        self.tmp.cleanup()

    def run_trigger(self, marker: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "AH_WORKSPACE": str(self.root), "AH_FAKE_RUN": marker}
        return subprocess.run(
            ["bash", "-euo", "pipefail", "-c", self.SCRIPT, "test", str(ROOT), "standup"],
            env=env, text=True, capture_output=True,
        )

    def test_second_run_receives_the_first_runs_memo(self):
        first = self.run_trigger("one")
        self.assertEqual(0, first.returncode, first.stderr)
        # Nothing to recall yet, so the first prompt must not claim otherwise.
        self.assertNotIn("PREVIOUS RUNS", first.stdout)

        second = self.run_trigger("two")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertIn("PREVIOUS RUNS", second.stdout)
        self.assertIn("run one finished", second.stdout)

    def test_run_asks_the_agent_for_a_memo_line(self):
        result = self.run_trigger("one")
        self.assertIn("MEMO:", result.stdout)

    def test_memory_file_records_the_run(self):
        self.run_trigger("one")
        stored = json.loads(
            (self.root / "agents" / "memory" / "trigger-runs.json").read_text())
        self.assertEqual(1, len(stored["standup"]))
        self.assertEqual(0, stored["standup"][-1]["status"])


if __name__ == "__main__":
    unittest.main()
