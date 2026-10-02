"""Regression coverage for the Telegram task-management control surface."""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


LIB = Path(__file__).resolve().parents[1] / "bin" / "lib"
ROOT = LIB.parents[1]
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


class TelegramTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.tmp.name)
        (self.workspace / "agents" / "tasks").mkdir(parents=True)
        (self.workspace / "agents" / "reports").mkdir(parents=True)
        (self.workspace / "agents" / "roles").mkdir(parents=True)
        (self.workspace / "agents" / "task-templates").mkdir(parents=True)
        shutil.copy2(ROOT / "agents" / "task-templates" / "task.md",
                     self.workspace / "agents" / "task-templates" / "task.md")
        (self.workspace / "worktrees").mkdir()
        self.old_workspace = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(self.workspace)
        for name in ("state", "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)
        self.state = importlib.import_module("state")
        self.tgcore = importlib.import_module("tgcore")
        self.tgcmd = importlib.import_module("tgcmd")
        self.tgtask = importlib.import_module("tgtask")
        self.tgwatch = importlib.import_module("tgwatch")
        self.tgbot = importlib.import_module("tgbot")

    def tearDown(self):
        if self.old_workspace is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.old_workspace
        self.tmp.cleanup()

    def task(self, task_id="task-101"):
        path = self.state.TASKS / f"{task_id}.md"
        path.write_text(
            f"# Task: Test task\n\n- **ID:** {task_id}\n- **Role:** lead\n"
            "\n## Acceptance criteria\n- [ ] first\n- [ ] second\n\n## Required checks\n"
        )
        return path

    def test_unpaired_chat_cannot_dispatch_mutating_commands(self):
        cfg = {"allowed": []}
        sent = []
        mutation = unittest.mock.Mock(return_value="MUTATED")
        with patch.object(self.tgcore, "allowed_from_env", return_value=[]), \
             patch.object(self.tgcore, "send", side_effect=lambda *args: sent.append(args)), \
             patch.dict(self.tgtask.HANDLERS, {"assign": mutation}):
            self.tgbot._dispatch(cfg, {"chat": {"id": 77, "username": "stranger"},
                                       "text": "/assign task-101 backend"})
        mutation.assert_not_called()
        self.assertIn("belum terhubung", sent[0][1])

    def test_allowed_chat_dispatches_each_required_mutation(self):
        cfg = {"allowed": [77]}
        sent = []
        for command in ("new", "assign", "wt", "tick"):
            mutation = unittest.mock.Mock(return_value="done")
            with patch.object(self.tgcore, "send", side_effect=lambda *args: sent.append(args)), \
                 patch.dict(self.tgtask.HANDLERS, {command: mutation}):
                self.tgbot._dispatch(cfg, {"chat": {"id": 77}, "text": f"/{command} args"})
            mutation.assert_called_once_with("args")

    def test_assign_and_tick_mutate_only_existing_task(self):
        task = self.task()
        self.assertIn("ditetapkan", self.tgtask.cmd_assign("task-101 backend"))
        self.assertIn("**Role:** backend", task.read_text())
        self.assertIn("dicentang", self.tgtask.cmd_tick("task-101 1"))
        self.assertIn("- [x] first", task.read_text())
        self.assertIn("Task tidak ditemukan", self.tgtask.cmd_assign("task-999 backend"))
        self.assertIn("Task tidak ditemukan", self.tgtask.cmd_tick("task-999 1"))

    def test_successful_new_creates_a_task_that_appears_in_listing(self):
        def create_task(args, timeout=60):
            self.assertEqual(["task", "new", "Created from Telegram"], args)
            self.assertEqual(60, timeout)
            self.task("task-102")
            return True, "Created task-102"

        with patch.object(self.tgtask, "_run", side_effect=create_task):
            response = self.tgtask.cmd_new("Created from Telegram")

        self.assertIn("task-102", response)
        self.assertIn("task-102", [task["id"] for task in self.state.tasks()])

    def test_real_task_new_preserves_shell_sensitive_and_unicode_title(self):
        title = "R&D | \\ bahasa Indonesia ✓"
        env = {**os.environ, "AH_WORKSPACE": str(self.workspace)}
        result = subprocess.run([str(ROOT / "bin" / "ah"), "task", "new", title],
                                capture_output=True, text=True, env=env, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        task = (self.workspace / "agents" / "tasks" / "task-001.md").read_text()
        self.assertIn(f"# Task: {title}", task)

    def test_real_task_new_rejects_newline_title_without_creating_task(self):
        env = {**os.environ, "AH_WORKSPACE": str(self.workspace)}
        result = subprocess.run([str(ROOT / "bin" / "ah"), "task", "new", "first\nsecond"],
                                capture_output=True, text=True, env=env, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("single line", result.stderr)
        self.assertFalse((self.workspace / "agents" / "tasks" / "task-001.md").exists())

    def test_worktree_requires_an_existing_task_id(self):
        with patch.object(self.tgtask, "_run") as run:
            response = self.tgtask.cmd_wt("task-999 projects/sandbox")
        run.assert_not_called()
        self.assertIn("Task tidak ditemukan", response)

    def test_worktree_runs_expected_cli_for_existing_canonical_task(self):
        self.task()
        with patch.object(self.tgtask, "_run", return_value=(True, "worktree ready")) as run:
            response = self.tgtask.cmd_wt("task-101 projects/sandbox")
        run.assert_called_once_with(["wt", "add", "task-101", "projects/sandbox"], timeout=90)
        self.assertIn("Worktree dibuat", response)
        self.assertIn("worktree ready", response)

    def test_task_id_cannot_escape_task_directory(self):
        outside = self.workspace / "agents" / "outside.md"
        outside.write_text("original")
        self.assertIn("Task tidak ditemukan", self.tgtask.cmd_note("../outside no-touch"))
        self.assertEqual("original", outside.read_text())

    def test_malicious_task_ids_are_rejected_by_shared_mutation_commands(self):
        malicious_ids = ("../outside", "task-abc", "task-101/../../outside", "task-101.md")
        for task_id in malicious_ids:
            with self.subTest(task_id=task_id):
                commands = (
                    lambda: self.tgtask.cmd_assign(f"{task_id} backend"),
                    lambda: self.tgtask.cmd_ac(f"{task_id} a criterion"),
                    lambda: self.tgtask.cmd_tick(f"{task_id} 1"),
                    lambda: self.tgtask.cmd_note(f"{task_id} no-touch"),
                    lambda: self.tgtask.cmd_wt(f"{task_id} projects/sandbox"),
                )
                with patch.object(self.tgtask, "_run") as run:
                    for command in commands:
                        self.assertIn("Task tidak ditemukan", command())
                run.assert_not_called()

    def test_notifications_include_only_completion_events_and_respect_quiet(self):
        job = {"id": "job-1", "status": "done", "role": "backend", "elapsed": 2, "task": "task-101"}
        task = {"id": "task-101", "criteria_done": 2, "criteria_total": 2,
                "status": "review", "title": "Test task"}
        watch = {"jobs": {"job-1": "running"}, "tasks": {"task-101": "1/2:active"},
                 "primed": True, "quiet": False}
        with patch("jobs.listing", return_value=[job]), \
             patch.object(self.state, "tasks", return_value=[task]), \
             patch.object(self.tgwatch, "_outcome", return_value="done"):
            events = self.tgwatch.detect(watch)
        self.assertEqual(2, len(events))
        self.assertTrue(all("job-1" in event or "task-101" in event for event in events))

        with patch.object(self.tgwatch, "load", return_value={"quiet": False}), \
             patch.object(self.tgwatch, "save") as save:
            self.assertIn("dimatikan", self.tgwatch.cmd_quiet("on"))
            self.assertTrue(save.call_args.args[0]["quiet"])
        with patch.object(self.tgwatch, "load", return_value={"quiet": True}), \
             patch.object(self.tgwatch, "save") as save:
            self.assertIn("dinyalakan", self.tgwatch.cmd_quiet("off"))
            self.assertFalse(save.call_args.args[0]["quiet"])
        self.assertIn("Ringkasan", self.tgwatch.cmd_digest(""))

    def test_routine_and_repeated_polls_do_not_repeat_notifications(self):
        routine = {"id": "task-101", "criteria_done": 1, "criteria_total": 2,
                   "status": "active", "title": "Test task"}
        complete = {**routine, "criteria_done": 2, "status": "review"}
        watch = {"jobs": {}, "tasks": {"task-101": "1/2:active"}, "primed": True}
        with patch("jobs.listing", return_value=[]), patch.object(self.state, "tasks", return_value=[routine]):
            self.assertEqual([], self.tgwatch.detect(watch))
        with patch("jobs.listing", return_value=[]), patch.object(self.state, "tasks", return_value=[complete]):
            event = self.tgwatch.detect(watch)
        self.assertEqual(1, len(event))
        with patch("jobs.listing", return_value=[]), patch.object(self.state, "tasks", return_value=[complete]):
            self.assertEqual([], self.tgwatch.detect(watch))

    def test_notify_sends_only_important_events_and_skips_quiet_mode(self):
        cfg = {"allowed": [77]}
        watcher = {"quiet": False, "primed": True}
        with patch.object(self.tgwatch, "load", return_value=watcher), \
             patch.object(self.tgwatch, "prime"), \
             patch.object(self.tgwatch, "detect", return_value=["important"]), \
             patch.object(self.tgwatch, "save"), \
             patch.object(self.tgcore, "send") as send:
            self.tgbot._notify(cfg)
        send.assert_called_once_with(77, "important")

        watcher["quiet"] = True
        with patch.object(self.tgwatch, "load", return_value=watcher), \
             patch.object(self.tgwatch, "prime"), \
             patch.object(self.tgwatch, "detect", return_value=["important"]), \
             patch.object(self.tgwatch, "save"), \
             patch.object(self.tgcore, "send") as send:
            self.tgbot._notify(cfg)
        send.assert_not_called()

    def test_transport_dispatch_is_mocked_and_splits_long_messages(self):
        payloads = []

        def call(method, params, timeout=40):
            payloads.append((method, params, timeout))
            return {"ok": True}

        with patch.object(self.tgcore, "call", side_effect=call):
            response = self.tgcore.send(77, "a" * (self.tgcore.TG_LIMIT + 1))

        self.assertTrue(response["ok"])
        self.assertEqual(2, len(payloads))
        self.assertTrue(all(method == "sendMessage" for method, _, _ in payloads))
        self.assertTrue(all(params["chat_id"] == 77 for _, params, _ in payloads))


if __name__ == "__main__":
    unittest.main()
