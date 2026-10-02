"""Reading #daily-updates without an agent, an engine, or a permission gate.

A lead agent was asked to summarise this channel and correctly stopped: the
harness has no Slack credential, and `ops/harness/claude-settings.json` denies
curl and wget outright. Its report was accurate.

The fix is not to loosen that. It is to make the read a plain harness capability
like /weekly: deterministic, running inside the bot process, costing no engine
spend and touching no permission gate. It groups and attributes what was
actually posted -- it does not paraphrase, so it cannot invent an update nobody
wrote.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))
import slackread  # noqa: E402


# Thu 2026-09-17 20:00 WIB
NOW = 1789657200.0


def msg(ts, user, text, **kw):
    base = {"ts": str(ts), "user": user, "text": text, "type": "message"}
    base.update(kw)
    return base


class WindowTests(unittest.TestCase):
    def test_the_week_starts_on_monday_in_the_team_timezone(self):
        oldest, latest = slackread.week_window(NOW)
        self.assertEqual("2026-09-14", slackread.day_label(oldest))
        self.assertEqual("2026-09-17", slackread.day_label(latest))

    def test_a_monday_still_reports_that_same_monday(self):
        monday = 1789318800.0 + 3600 * 9      # Mon 2026-09-14 09:00 WIB
        oldest, _ = slackread.week_window(monday)
        self.assertEqual("2026-09-14", slackread.day_label(oldest))


class GroupingTests(unittest.TestCase):
    def setUp(self):
        self.messages = [
            msg(1789639782, "U_DIKY", "Hari ini ngerjain\n• Module A (Done)"),
            msg(1789551757, "U_DIKY", "Update 16 Sep\n• Module B (Done)"),
            msg(1789551588, "U_RAFIF", "Update daily\n• Migrasi select (Done)"),
        ]
        self.names = {"U_DIKY": "Diky", "U_RAFIF": "Rafif"}

    def test_messages_are_grouped_by_day_newest_day_last(self):
        days = slackread.by_day(self.messages)
        self.assertEqual(["2026-09-16", "2026-09-17"], [d["date"] for d in days])

    def test_each_day_lists_who_posted(self):
        days = slackread.by_day(self.messages, self.names)
        self.assertEqual(["Rafif", "Diky"], [e["author"] for e in days[0]["entries"]])

    def test_an_unknown_user_id_is_shown_rather_than_dropped(self):
        # users:read may not be granted; a missing name must not lose the post.
        days = slackread.by_day([msg(1789639782, "U_NEW", "hello")], {})
        self.assertEqual("U_NEW", days[0]["entries"][0]["author"])

    def test_bot_noise_is_left_out(self):
        noisy = self.messages + [msg(1789610870, "USLACKBOT", "A huddle started",
                                     subtype="huddle_thread")]
        self.assertNotIn("A huddle started", str(slackread.by_day(noisy)))

    def test_a_day_with_no_posts_is_reported_as_silent(self):
        report = slackread.render(slackread.collect(self.messages, self.names, NOW))
        self.assertIn("2026-09-14", report)
        self.assertIn("tidak ada", report.lower())


class ReportTests(unittest.TestCase):
    def test_who_did_not_report_is_named(self):
        # The point of a daily channel is noticing silence.
        data = slackread.collect(
            [msg(1789639782, "U_A", "update")], {"U_A": "A", "U_B": "B"}, NOW,
            expected={"U_A", "U_B"})
        self.assertIn("B", data["missing"])
        self.assertNotIn("A", data["missing"])

    def test_the_same_input_renders_the_same_report(self):
        m = [msg(1789639782, "U_A", "update")]
        self.assertEqual(slackread.report(m, {"U_A": "A"}, NOW),
                         slackread.report(m, {"U_A": "A"}, NOW))

    def test_slack_markup_is_escaped_for_telegram(self):
        m = [msg(1789639782, "U_A", "fix <script> & co")]
        out = slackread.report(m, {"U_A": "A"}, NOW)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>", out)

    def test_slack_user_mentions_are_rendered_readably(self):
        m = [msg(1789639782, "U_A", "<@U_B|Diky> tolong cek")]
        out = slackread.report(m, {"U_A": "A", "U_B": "Diky"}, NOW)
        self.assertIn("@Diky", out)
        self.assertNotIn("U_B|", out)

    def test_slack_links_keep_the_label_not_the_angle_brackets(self):
        m = [msg(1789639782, "U_A", "lihat <https://x.co/y|x.co/y> ya")]
        out = slackread.report(m, {"U_A": "A"}, NOW)
        self.assertIn("x.co/y", out)
        self.assertNotIn("<https", out)

    def test_it_stays_within_one_telegram_message(self):
        many = [msg(1789639782 + i, f"U_{i}", "x" * 300) for i in range(40)]
        self.assertLess(len(slackread.report(many, {}, NOW)), 4096)


class CredentialTests(unittest.TestCase):
    def test_it_refuses_to_run_without_a_token_instead_of_guessing(self):
        with self.assertRaises(slackread.NotConfigured):
            slackread.fetch_week(token="", channel="C123", now=NOW)

    def test_it_refuses_without_a_channel_id(self):
        with self.assertRaises(slackread.NotConfigured):
            slackread.fetch_week(token="xoxb-x", channel="", now=NOW)

    def test_the_error_names_the_settings_the_operator_must_add(self):
        try:
            slackread.fetch_week(token="", channel="", now=NOW)
        except slackread.NotConfigured as exc:
            self.assertIn("SLACK_BOT_TOKEN", str(exc))
            self.assertIn("SLACK_DAILY_CHANNEL_ID", str(exc))

    def test_a_token_is_never_placed_in_a_url(self):
        # Slack wants it in the Authorization header; a URL lands in logs.
        source = (ROOT / "bin" / "lib" / "slackread.py").read_text(encoding="utf-8")
        self.assertNotIn("token=", source)
        self.assertIn("Authorization", source)


if __name__ == "__main__":
    unittest.main()


class TelegramWiringTests(unittest.TestCase):
    """Reachable from the chat, and honest when it cannot run."""

    def setUp(self):
        import importlib, os, tempfile
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        workspace = Path(self.tmp.name)
        for subdir in ("tasks", "reports", "roles", "claims"):
            (workspace / "agents" / subdir).mkdir(parents=True)
        (workspace / "worktrees").mkdir()
        (workspace / "AGENTS.md").write_text("rules")
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = str(workspace)
        for name in ("state", "jobs", "tgcore", "tgcmd", "tgtask", "tgwatch", "tgbot"):
            sys.modules.pop(name, None)
        self.tgcmd = importlib.import_module("tgcmd")
        self.tgcore = importlib.import_module("tgcore")
        self.tgbot = importlib.import_module("tgbot")

    def tearDown(self):
        import os
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()

    def test_daily_is_dispatchable(self):
        self.assertIn("daily", self.tgcmd.HANDLERS)

    def test_daily_is_aggregate_reporting_so_an_operator_may_read_it(self):
        self.assertEqual("operator", self.tgbot.COMMAND_LEVELS.get("daily"))

    def test_daily_appears_in_help_and_in_the_slash_menu(self):
        self.assertIn("/daily", self.tgcmd.cmd_help(""))
        self.assertIn("daily", {n for n, _ in self.tgcore._full_command_list()})

    def test_without_a_token_it_explains_the_setup_instead_of_erroring(self):
        import os
        for key in ("SLACK_BOT_TOKEN", "SLACK_DAILY_CHANNEL_ID"):
            os.environ.pop(key, None)
        out = self.tgcmd.cmd_daily("")
        self.assertIn("SLACK_BOT_TOKEN", out)
        self.assertIn("channels:history", out)
        self.assertNotIn("Traceback", out)


class OperationsSurfaceTests(unittest.TestCase):
    """/ops must not keep calling Slack "not-configured" once it is."""

    def setUp(self):
        import importlib, os, tempfile
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.previous = os.environ.get("AH_WORKSPACE")
        os.environ["AH_WORKSPACE"] = self.tmp.name
        for name in ("state", "operations"):
            sys.modules.pop(name, None)
        self.operations = importlib.import_module("operations")
        self._saved = {k: os.environ.get(k)
                       for k in ("SLACK_BOT_TOKEN", "SLACK_DAILY_CHANNEL_ID")}

    def tearDown(self):
        import os
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if self.previous is None:
            os.environ.pop("AH_WORKSPACE", None)
        else:
            os.environ["AH_WORKSPACE"] = self.previous
        self.tmp.cleanup()

    def slack_row(self):
        links = self.operations.snapshot()["links"]
        return next(l for l in links if l["label"].startswith("Slack"))

    def test_slack_reads_not_configured_without_a_token(self):
        import os
        os.environ.pop("SLACK_BOT_TOKEN", None)
        os.environ.pop("SLACK_DAILY_CHANNEL_ID", None)
        self.assertEqual("not-configured", self.slack_row()["status"])

    def test_slack_reads_ready_once_both_settings_exist(self):
        import os
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test"
        os.environ["SLACK_DAILY_CHANNEL_ID"] = "C123"
        self.assertEqual("ready", self.slack_row()["status"])

    def test_a_channel_without_a_token_is_still_not_configured(self):
        import os
        os.environ.pop("SLACK_BOT_TOKEN", None)
        os.environ["SLACK_DAILY_CHANNEL_ID"] = "C123"
        self.assertEqual("not-configured", self.slack_row()["status"])

    def test_the_token_is_never_exposed_in_the_surface(self):
        import os
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-supersecret"
        os.environ["SLACK_DAILY_CHANNEL_ID"] = "C123"
        self.assertNotIn("supersecret", str(self.operations.snapshot()))
