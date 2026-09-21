"""An engine the account is not authorised to use must not keep being chosen.

The harness ran every job through `claude`. On this machine the default
credentials belong to an org that has disabled Claude Code, so every run died
with "Your organization has disabled Claude subscription access for Claude
Code" — instantly, identically, forever, while `codex` sat installed and idle.

These tests pin the recovery: recognise that refusal, remember it, and pick the
next engine instead.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))

REFUSAL = ("Your organization has disabled Claude subscription access for "
           "Claude Code · Use an Anthropic API key instead, or ask your "
           "admin to enable access")


def _wait(jobs, jid, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        meta = jobs.refresh(jid)
        if meta and jobs.status(meta) != "running":
            return meta
        time.sleep(0.05)
    raise AssertionError(f"job {jid} never finished")


class EngineHealthTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        os.environ.pop("AH_ENGINE", None)
        os.environ.pop("AH_ENGINE_ORDER", None)
        for mod in ("state", "engine"):
            sys.modules.pop(mod, None)
        import engine
        self.engine = engine
        self.installed = {"claude", "codex"}

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_ENGINE", "AH_ENGINE_ORDER"):
            os.environ.pop(var, None)
        for mod in ("state", "engine"):
            sys.modules.pop(mod, None)

    def _pick(self, role="backend"):
        return self.engine.pick(role, is_installed=lambda n: n in self.installed)

    # --- recognising the refusal -------------------------------------------

    def test_the_real_refusal_is_recognised(self):
        self.assertTrue(self.engine.is_auth_refusal(REFUSAL))

    def test_an_api_key_refusal_is_recognised(self):
        self.assertTrue(self.engine.is_auth_refusal(
            "Invalid API key · Please run /login"))

    def test_ordinary_failure_is_not_an_auth_refusal(self):
        """A crash must not get an engine banned — only a refusal does."""
        self.assertFalse(self.engine.is_auth_refusal(
            "TypeError: cannot read property 'x' of undefined\nexit 1"))
        self.assertFalse(self.engine.is_auth_refusal(""))

    def test_an_agent_discussing_auth_is_not_a_refusal(self):
        """The adversarial case, and the reason this is not a plain substring match.

        Agents in this harness review auth code for a living. A qa run that
        fails a test whose name contains "invalid api key" must not get the
        engine banned — that would migrate every future run to another vendor
        for a reason no operator could ever find.
        """
        transcript = (
            "I read Backend/internal/middleware/permissions.go and traced the\n"
            "NULL app_role_id bypass. " + ("analysis. " * 200) + "\n"
            "FAIL tests/auth_test.go::test_invalid_api_key_is_rejected\n"
            "assert err.code == \"authentication_error\"\n"
            "1 test failed\n"
        )
        self.assertFalse(self.engine.is_auth_refusal(transcript))

    def test_a_refusal_is_recognised_even_after_a_short_banner(self):
        """Real refusals arrive at the top, but not always on byte zero."""
        self.assertTrue(self.engine.is_auth_refusal("starting\u2026\n" + REFUSAL))

    # --- choosing an engine -------------------------------------------------

    def test_preferred_engine_wins_when_nothing_is_blocked(self):
        self.assertEqual(self._pick(), "claude")

    def test_blocked_engine_is_skipped(self):
        self.engine.mark_blocked("claude", REFUSAL)
        self.assertEqual(self._pick(), "codex")

    def test_uninstalled_engine_is_skipped(self):
        self.installed = {"codex"}
        self.assertEqual(self._pick(), "codex")

    def test_explicit_override_beats_a_block(self):
        """AH_ENGINE is the operator speaking; the cache must not argue."""
        self.engine.mark_blocked("codex", REFUSAL)
        os.environ["AH_ENGINE"] = "codex"
        self.assertEqual(self._pick(), "codex")

    def test_order_is_configurable(self):
        os.environ["AH_ENGINE_ORDER"] = "codex,claude"
        self.assertEqual(self._pick(), "codex")

    def test_every_engine_blocked_still_returns_one(self):
        """Refusing to pick would strand the operator with no way back."""
        for name in ("claude", "codex"):
            self.engine.mark_blocked(name, REFUSAL)
        self.assertIn(self._pick(), ("claude", "codex"))

    def test_clearing_restores_the_engine(self):
        self.engine.mark_blocked("claude", REFUSAL)
        self.engine.clear("claude")
        self.assertEqual(self._pick(), "claude")

    def test_block_records_why_and_when(self):
        self.engine.mark_blocked("claude", REFUSAL)
        entry = self.engine.blocked()["claude"]
        self.assertIn("disabled Claude subscription", entry["reason"])
        self.assertLessEqual(entry["at"], time.time())

    def test_state_survives_a_restart(self):
        self.engine.mark_blocked("claude", REFUSAL)
        sys.modules.pop("engine", None)
        import engine as reloaded
        self.assertIn("claude", reloaded.blocked())

    def test_a_corrupt_state_file_does_not_break_the_harness(self):
        self.engine.STATE.write_text("{ not json")
        self.assertEqual(self.engine.blocked(), {})
        self.assertEqual(self._pick(), "claude")


class JobFallbackTests(unittest.TestCase):
    """The block must be recorded by the thing that actually sees the failure."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        root = Path(self._tmp.name)
        (root / "agents" / "roles").mkdir(parents=True)
        for name in ("_common", "lead"):
            (root / "agents" / "roles" / f"{name}.md").write_text("Read only")
        (root / "AGENTS.md").write_text("rules")
        self.bindir = root / "fakebin"
        self.bindir.mkdir()

        os.environ["AH_WORKSPACE"] = str(root)
        os.environ.pop("AH_ENGINE", None)
        os.environ.pop("AH_ENGINE_ORDER", None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)
        import state  # noqa: F401
        import engine
        import jobs
        self.engine, self.jobs, self.root = engine, jobs, root
        jobs.EXTRA_PATHS = [self.bindir, *jobs.EXTRA_PATHS]

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_ENGINE", "AH_ENGINE_ORDER"):
            os.environ.pop(var, None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)

    def _fake(self, name: str, body: str) -> None:
        path = self.bindir / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def test_a_refusing_engine_is_blocked_after_the_run(self):
        self._fake("claude", f'echo "{REFUSAL}"\nexit 1')
        jid = self.jobs.spawn(role="lead", prompt="x", engine="claude")["id"]
        meta = _wait(self.jobs, jid)
        self.assertEqual(self.jobs.status(meta), "failed")
        self.assertIn("claude", self.engine.blocked())

    def test_the_next_run_picks_the_other_engine(self):
        self._fake("claude", f'echo "{REFUSAL}"\nexit 1')
        self._fake("codex", 'echo "## Report"\nexit 0')
        _wait(self.jobs, self.jobs.spawn(role="lead", prompt="x")["id"])
        second = _wait(self.jobs, self.jobs.spawn(role="lead", prompt="y")["id"])
        self.assertEqual(second["engine"], "codex")
        self.assertEqual(self.jobs.status(second), "done")

    def test_an_ordinary_crash_does_not_block_the_engine(self):
        self._fake("claude", 'echo "segfault"\nexit 139')
        jid = self.jobs.spawn(role="lead", prompt="x", engine="claude")["id"]
        _wait(self.jobs, jid)
        self.assertNotIn("claude", self.engine.blocked())

    def test_a_long_transcript_that_merely_mentions_auth_does_not_block(self):
        """The failure this guards against is silent and undiagnosable."""
        self._fake("claude",
                   'echo "reviewing the auth middleware"\n'
                   'i=0; while [ $i -lt 400 ]; do echo "line $i of analysis"; i=$((i+1)); done\n'
                   'echo "FAIL test_invalid_api_key_is_rejected"\n'
                   'echo "authentication_error"\n'
                   'exit 1')
        jid = self.jobs.spawn(role="lead", prompt="x", engine="claude")["id"]
        _wait(self.jobs, jid)
        self.assertNotIn("claude", self.engine.blocked())

    def test_a_successful_run_clears_an_earlier_block(self):
        """Once the admin re-enables access, the harness must come back on its own."""
        self.engine.mark_blocked("claude", REFUSAL)
        self._fake("claude", 'echo "## Report"\nexit 0')
        jid = self.jobs.spawn(role="lead", prompt="x", engine="claude")["id"]
        _wait(self.jobs, jid)
        self.assertNotIn("claude", self.engine.blocked())


LIMIT = ("ERROR: You've hit your usage limit. Upgrade to Pro "
         "(https://chatgpt.com/explore/pro), visit "
         "https://chatgpt.com/codex/settings/usage to purchase more credits "
         "or try again at 3:56 AM.")


class LimitTests(unittest.TestCase):
    """A usage limit is not a refusal. It ends by itself, at a stated time."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self._tmp.name)
        (self.root / "agents").mkdir(parents=True)
        os.environ["AH_WORKSPACE"] = str(self.root)
        os.environ.pop("AH_ENGINE", None)
        os.environ.pop("AH_ENGINE_ORDER", None)
        for mod in ("state", "engine"):
            sys.modules.pop(mod, None)
        import engine
        self.engine = engine
        self.installed = {"claude", "codex"}

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_ENGINE", "AH_ENGINE_ORDER"):
            os.environ.pop(var, None)
        for mod in ("state", "engine"):
            sys.modules.pop(mod, None)

    def _here(self, n):
        return n in self.installed

    def test_a_usage_limit_is_classified_as_limited_not_refused(self):
        self.assertEqual(self.engine.classify(LIMIT), self.engine.KIND_LIMITED)

    def test_an_org_refusal_is_classified_as_refused(self):
        self.assertEqual(self.engine.classify(REFUSAL), self.engine.KIND_REFUSED)

    def test_an_ordinary_crash_is_classified_as_nothing(self):
        self.assertIsNone(self.engine.classify("TypeError: undefined\nexit 1"))

    def test_the_stated_retry_time_is_parsed(self):
        when = self.engine.retry_at(LIMIT)
        self.assertIsNotNone(when)
        self.assertGreater(when, time.time())
        self.assertEqual(time.localtime(when).tm_hour, 3)
        self.assertEqual(time.localtime(when).tm_min, 56)

    def test_a_limit_without_a_time_still_gets_a_cooldown(self):
        self.engine.note_result("codex", False, "You have hit your rate limit.")
        entry = self.engine.unavailable()["codex"]
        self.assertEqual(entry["kind"], self.engine.KIND_LIMITED)
        self.assertGreater(entry["until"], time.time())

    def test_a_limit_expires_on_its_own(self):
        """Nobody should have to run a command to undo a limit that has passed."""
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT,
                         until=time.time() - 1)
        self.assertNotIn("codex", self.engine.unavailable())
        self.assertEqual(self.engine.pick(is_installed=self._here), "claude")

    def test_a_refusal_does_not_expire(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, REFUSAL)
        self.assertIn("claude", self.engine.unavailable())

    # --- rotation, both directions -----------------------------------------

    def test_a_limited_engine_rotates_back_to_the_other_one(self):
        """The owner's case: codex hits its limit, so go back to claude."""
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT,
                         until=time.time() + 3600)
        os.environ["AH_ENGINE_ORDER"] = "codex claude"
        self.assertEqual(self.engine.pick(is_installed=self._here), "claude")

    def test_rotation_is_not_one_way(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, REFUSAL)
        self.assertEqual(self.engine.pick(is_installed=self._here), "codex")
        self.engine.clear("claude")
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT,
                         until=time.time() + 3600)
        self.assertEqual(self.engine.pick(is_installed=self._here), "claude")

    # --- pause --------------------------------------------------------------

    def test_paused_when_every_engine_is_out(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, REFUSAL)
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT,
                         until=time.time() + 3600)
        self.assertTrue(self.engine.paused(is_installed=self._here))
        self.assertEqual(self.engine.available(is_installed=self._here), [])

    def test_not_paused_while_one_engine_survives(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, REFUSAL)
        self.assertFalse(self.engine.paused(is_installed=self._here))

    def test_pause_lifts_itself_when_the_limit_expires(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, REFUSAL)
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT,
                         until=time.time() - 1)
        self.assertFalse(self.engine.paused(is_installed=self._here))

    def test_next_free_at_reports_the_earliest_return(self):
        soon, later = time.time() + 60, time.time() + 600
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT, until=later)
        self.engine.mark("claude", self.engine.KIND_LIMITED, LIMIT, until=soon)
        self.assertAlmostEqual(self.engine.next_free_at(), soon, delta=1)

    def test_next_free_at_is_unknown_when_only_refusals_remain(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, REFUSAL)
        self.engine.mark("codex", self.engine.KIND_REFUSED, REFUSAL)
        self.assertIsNone(self.engine.next_free_at())


class RetryTests(unittest.TestCase):
    """Three attempts, rotating engines, then stop — do not burn the quota."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        root = Path(self._tmp.name)
        (root / "agents" / "roles").mkdir(parents=True)
        for name in ("_common", "lead"):
            (root / "agents" / "roles" / f"{name}.md").write_text("Read only")
        (root / "AGENTS.md").write_text("rules")
        self.bindir = root / "fakebin"
        self.bindir.mkdir()
        os.environ["AH_WORKSPACE"] = str(root)
        os.environ.pop("AH_ENGINE", None)
        os.environ.pop("AH_ENGINE_ORDER", None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)
        import state  # noqa: F401
        import engine
        import jobs
        self.engine, self.jobs, self.root = engine, jobs, root
        jobs.EXTRA_PATHS = [self.bindir, *jobs.EXTRA_PATHS]

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_ENGINE", "AH_ENGINE_ORDER"):
            os.environ.pop(var, None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)

    def _fake(self, name: str, body: str) -> None:
        path = self.bindir / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def test_max_attempts_is_three(self):
        self.assertEqual(self.engine.MAX_ATTEMPTS, 3)

    def test_a_limited_run_is_retried_on_the_other_engine(self):
        self._fake("codex", f'echo "{LIMIT}"\nexit 1')
        self._fake("claude", 'echo "## Report"\nexit 0')
        os.environ["AH_ENGINE_ORDER"] = "codex claude"
        first = _wait(self.jobs, self.jobs.spawn(role="lead", prompt="x")["id"])
        self.assertEqual(first["engine"], "codex")
        follow = self.jobs.retry_if_engine_failed(first["id"])
        self.assertIsNotNone(follow)
        follow = _wait(self.jobs, follow["id"])
        self.assertEqual(follow["engine"], "claude")
        self.assertEqual(self.jobs.status(follow), "done")
        self.assertEqual(follow["attempt"], 2)

    def test_retry_stops_after_three_attempts(self):
        self._fake("codex", f'echo "{LIMIT}"\nexit 1')
        self._fake("claude", f'echo "{LIMIT}"\nexit 1')
        meta = _wait(self.jobs, self.jobs.spawn(role="lead", prompt="x")["id"])
        attempts = 1
        while True:
            nxt = self.jobs.retry_if_engine_failed(meta["id"])
            if nxt is None:
                break
            attempts += 1
            meta = _wait(self.jobs, nxt["id"])
            self.assertLessEqual(attempts, self.engine.MAX_ATTEMPTS)
        self.assertLessEqual(attempts, self.engine.MAX_ATTEMPTS)

    def test_an_ordinary_failure_is_never_retried(self):
        """Retrying a genuine bug on another vendor just burns two quotas."""
        self._fake("claude", 'echo "AssertionError"\nexit 1')
        meta = _wait(self.jobs, self.jobs.spawn(
            role="lead", prompt="x", engine="claude")["id"])
        self.assertIsNone(self.jobs.retry_if_engine_failed(meta["id"]))

    def test_spawning_while_paused_is_refused_not_wasted(self):
        self.engine.mark("claude", self.engine.KIND_REFUSED, REFUSAL)
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT,
                         until=time.time() + 3600)
        with self.assertRaises(ValueError) as caught:
            self.jobs.spawn(role="lead", prompt="x")
        self.assertIn("paused", str(caught.exception).lower())


class ExitCodeLiesTests(unittest.TestCase):
    """An engine that fails while exiting 0 must still be believed.

    Observed on codex 0.154.0: it printed "You've hit your usage limit" and
    exited 0. Keying the whole rotation off the exit code meant the harness
    read that as a successful run, cleared the engine's record, and handed it
    the next job. It also echoes the prompt first, so its error lands at the
    END of the output — the opposite end from claude's.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        root = Path(self._tmp.name)
        (root / "agents" / "roles").mkdir(parents=True)
        for name in ("_common", "lead"):
            (root / "agents" / "roles" / f"{name}.md").write_text("Read only")
        (root / "AGENTS.md").write_text("rules")
        self.bindir = root / "fakebin"
        self.bindir.mkdir()
        os.environ["AH_WORKSPACE"] = str(root)
        os.environ.pop("AH_ENGINE", None)
        os.environ.pop("AH_ENGINE_ORDER", None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)
        import state  # noqa: F401
        import engine
        import jobs
        self.engine, self.jobs = engine, jobs
        jobs.EXTRA_PATHS = [self.bindir, *jobs.EXTRA_PATHS]

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_ENGINE", "AH_ENGINE_ORDER"):
            os.environ.pop(var, None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)

    def _fake(self, name, body):
        path = self.bindir / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def test_a_limit_at_the_end_of_the_output_is_seen(self):
        """codex echoes the prompt first, so its error is the last thing said."""
        body = "the agent restated the objective\n" * 200 + LIMIT
        self.assertEqual(self.engine.classify(body), self.engine.KIND_LIMITED)

    def test_a_limit_with_exit_zero_still_blocks_the_engine(self):
        self._fake("codex", f'echo "prompt echo"\necho "{LIMIT}"\nexit 0')
        jid = self.jobs.spawn(role="lead", prompt="x", engine="codex")["id"]
        _wait(self.jobs, jid)
        self.assertIn("codex", self.engine.unavailable())

    def test_a_limit_with_exit_zero_is_not_reported_as_done(self):
        """A run that produced nothing must never reach Telegram as a green tick."""
        self._fake("codex", f'echo "{LIMIT}"\nexit 0')
        jid = self.jobs.spawn(role="lead", prompt="x", engine="codex")["id"]
        meta = _wait(self.jobs, jid)
        self.assertEqual(self.jobs.status(meta), "failed")

    def test_a_genuine_success_still_clears_the_record(self):
        self.engine.mark("codex", self.engine.KIND_LIMITED, LIMIT,
                         until=time.time() + 3600)
        self._fake("codex", 'echo "## Report"\necho "Scope done: everything"\nexit 0')
        jid = self.jobs.spawn(role="lead", prompt="x", engine="codex")["id"]
        _wait(self.jobs, jid)
        self.assertNotIn("codex", self.engine.unavailable())

    def test_an_agent_transcript_about_auth_is_still_not_a_refusal(self):
        """The guard from before must survive scanning both ends of the output."""
        body = ("reviewing permissions.go\n" * 50 +
                "FAIL tests/auth_test.go::test_invalid_api_key_is_rejected\n"
                "assert err.code == \"authentication_error\"\n1 test failed\n")
        self.assertIsNone(self.engine.classify(body))


class AutoResumeTests(unittest.TestCase):
    """A pause must end by itself. Nobody is awake at 3:56 AM to restart it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        root = Path(self._tmp.name)
        (root / "agents" / "roles").mkdir(parents=True)
        for name in ("_common", "lead"):
            (root / "agents" / "roles" / f"{name}.md").write_text("Read only")
        (root / "AGENTS.md").write_text("rules")
        self.bindir = root / "fakebin"
        self.bindir.mkdir()
        os.environ["AH_WORKSPACE"] = str(root)
        os.environ.pop("AH_ENGINE", None)
        os.environ["AH_ENGINE_ORDER"] = "codex claude"
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)
        import state  # noqa: F401
        import engine
        import jobs
        self.engine, self.jobs = engine, jobs
        jobs.EXTRA_PATHS = [self.bindir, *jobs.EXTRA_PATHS]

    def tearDown(self):
        self._tmp.cleanup()
        for var in ("AH_WORKSPACE", "AH_ENGINE", "AH_ENGINE_ORDER"):
            os.environ.pop(var, None)
        for mod in ("state", "engine", "jobs"):
            sys.modules.pop(mod, None)

    def _fake(self, name, body):
        path = self.bindir / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def _exhaust(self):
        """Drive one job until every engine is limited and it can go no further."""
        self._fake("codex", f'echo "{LIMIT}"\nexit 1')
        self._fake("claude", f'echo "{LIMIT}"\nexit 1')
        meta = _wait(self.jobs, self.jobs.spawn(role="lead", prompt="do the thing")["id"])
        while True:
            nxt = self.jobs.retry_if_engine_failed(meta["id"])
            if nxt is None:
                return meta
            meta = _wait(self.jobs, nxt["id"])

    def test_a_job_stalled_by_a_limit_is_marked_waiting_not_abandoned(self):
        last = self._exhaust()
        self.assertTrue(self.engine.paused())
        self.assertEqual(last.get("engine_fault"), self.engine.KIND_LIMITED)
        self.assertTrue(self.jobs.waiting())

    def test_tick_does_nothing_while_the_limit_holds(self):
        self._exhaust()
        self.assertEqual(self.jobs.tick(), [])

    def test_the_job_resumes_by_itself_once_the_limit_expires(self):
        last = self._exhaust()
        self._fake("codex", 'echo "## Report"\nexit 0')
        for name in ("codex", "claude"):
            self.engine.clear(name)

        started = self.jobs.tick()
        self.assertEqual(len(started), 1, "the waiting job should have resumed")
        resumed = _wait(self.jobs, started[0]["id"])
        self.assertEqual(self.jobs.status(resumed), "done")
        self.assertEqual(resumed["parent"], last["id"])
        self.assertIn("do the thing", (self.jobs.JOBS_DIR /
                                       f"{resumed['id']}.body").read_text())

    def test_a_resume_starts_its_attempt_budget_over(self):
        """Three attempts is a rotation budget, not a lifetime sentence."""
        self._exhaust()
        self._fake("codex", 'echo "## Report"\nexit 0')
        for name in ("codex", "claude"):
            self.engine.clear(name)
        resumed = _wait(self.jobs, self.jobs.tick()[0]["id"])
        self.assertEqual(resumed["attempt"], 1)
        self.assertEqual(resumed["resumes"], 1)

    def test_resuming_is_bounded_so_it_cannot_loop_for_ever(self):
        self.assertGreaterEqual(self.jobs.MAX_RESUMES, 1)
        self.assertLessEqual(self.jobs.MAX_RESUMES, 10)

    def test_a_refused_engine_alone_does_not_make_a_job_wait(self):
        """Refusals need a human. Queueing against one would wait for ever."""
        self._fake("codex", 'echo "AssertionError: boom"\nexit 1')
        meta = _wait(self.jobs, self.jobs.spawn(
            role="lead", prompt="x", engine="codex")["id"])
        self.assertFalse(self.jobs.waiting())
        self.assertIsNone(self.jobs.retry_if_engine_failed(meta["id"]))


if __name__ == "__main__":
    unittest.main()
