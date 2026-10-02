"""Triggers must actually get scheduled on Linux, with a usable environment.

Two defects made every scheduled trigger a no-op on the VPS:

  1. `ah trigger install` wrote a launchd plist unconditionally, so on Linux it
     created ~/Library/LaunchAgents and scheduled nothing. triggers.json showed
     four triggers `enabled: true` while `systemctl --user list-timers` had
     none of them.
  2. The systemd units supervise.sh generates carried only PATH and HOME. An
     agent started that way has no CLAUDE_CODE_OAUTH_TOKEN and answers
     "Not logged in - Please run /login", so even a scheduled run would fail.

These tests drive the real shell functions with systemctl stubbed out, so they
check the units that would be written rather than trusting the source text.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "bin" / "lib"


class TimerUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.bin = Path(self.tmp.name) / "bin"
        (self.home / ".config").mkdir(parents=True)
        self.bin.mkdir()
        # Stub the parts that would touch the real user manager.
        for name in ("systemctl", "loginctl"):
            stub = self.bin / name
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, schedule="daily 07:00"):
        script = textwrap.dedent(f"""
            set -e
            WORKSPACE={ROOT}
            die() {{ echo "$*" >&2; exit 1; }}
            . {LIB}/supervise.sh
            _sv_systemd_timer com.ah.trigger.standup "{schedule}" \\
                {ROOT}/bin/ah trigger run standup >/dev/null
        """)
        env = dict(os.environ, HOME=str(self.home),
                   PATH=f"{self.bin}:{os.environ['PATH']}",
                   XDG_CONFIG_HOME=str(self.home / ".config"))
        subprocess.run(["bash", "-c", script], check=True, env=env,
                       capture_output=True, text=True)
        unit_dir = self.home / ".config" / "systemd" / "user"
        return ((unit_dir / "com.ah.trigger.standup.service").read_text(),
                (unit_dir / "com.ah.trigger.standup.timer").read_text())

    def test_units_land_where_systemd_actually_looks(self):
        # XDG_CONFIG_HOME is the config dir itself. Appending ".config" again
        # wrote units to ~/.config/.config/systemd/user, which systemd ignores.
        self.install()
        good = self.home / ".config" / "systemd" / "user" / "com.ah.trigger.standup.timer"
        bad = self.home / ".config" / ".config" / "systemd" / "user"
        self.assertTrue(good.is_file(), f"unit not written to {good}")
        self.assertFalse(bad.exists(), f"unit written to the ignored path {bad}")

    def test_the_unit_loads_the_workspace_env_file(self):
        service, _ = self.install()
        self.assertIn("EnvironmentFile", service,
                      "without .env the agent has no engine credential")
        self.assertIn(".env", service)

    def test_a_missing_env_file_does_not_break_the_unit(self):
        # "-" prefix: optional. A workspace with no .env must still schedule.
        service, _ = self.install()
        self.assertIn("EnvironmentFile=-", service)

    def test_the_unit_tells_the_harness_where_the_workspace_is(self):
        service, _ = self.install()
        self.assertIn("AH_WORKSPACE=", service)

    def test_the_schedule_is_translated_into_an_oncalendar_line(self):
        _, timer = self.install("daily 07:00")
        self.assertIn("OnCalendar=", timer)
        self.assertIn("07:00:00", timer)

    def test_a_weekly_schedule_keeps_its_weekday(self):
        _, timer = self.install("weekly Mon 09:00")
        self.assertIn("Mon", timer)
        self.assertIn("09:00:00", timer)

    def test_a_missed_run_is_caught_up_rather_than_skipped(self):
        _, timer = self.install()
        self.assertIn("Persistent=true", timer)


class TriggerInstallPlatformTests(unittest.TestCase):
    """trigger.sh must delegate to supervise.sh instead of assuming a Mac."""

    def setUp(self):
        self.trigger = (LIB / "trigger.sh").read_text(encoding="utf-8")

    def test_install_goes_through_the_platform_abstraction(self):
        self.assertIn("sv_install_timer", self.trigger)

    def test_install_does_not_hardcode_a_launchagents_path(self):
        install = self.trigger.split("trg_install()", 1)[-1].split("\n}", 1)[0]
        self.assertNotIn("Library/LaunchAgents", install)

    def test_uninstall_goes_through_the_platform_abstraction(self):
        self.assertIn("sv_uninstall", self.trigger)

    def test_listing_does_not_decide_installed_state_from_a_plist_alone(self):
        listing = self.trigger.split("trg_list()", 1)[-1].split("\nPY", 1)[0]
        self.assertNotIn("LaunchAgents", listing)


if __name__ == "__main__":
    unittest.main()


class ScheduleTimezoneTests(TimerUnitTests):
    """"daily 07:00" must mean the same wall-clock time on every host.

    launchd reads StartCalendarInterval in the machine's local time, which on
    the team's Mac is WIB. A bare systemd OnCalendar is server-local, and this
    VPS runs UTC -- so the identical triggers.json entry meant 07:00 WIB on one
    machine and 14:00 WIB on the other. The timezone is therefore explicit.
    """

    def test_the_timer_pins_a_timezone_rather_than_inheriting_the_server_clock(self):
        _, timer = self.install("daily 07:00")
        self.assertRegex(timer, r"OnCalendar=.*07:00:00 \w+/\w+")

    def test_the_default_timezone_is_the_team_timezone(self):
        _, timer = self.install("daily 07:00")
        self.assertIn("Asia/Jakarta", timer)

    def test_the_timezone_can_be_overridden(self):
        env_before = os.environ.get("AH_SCHEDULE_TZ")
        os.environ["AH_SCHEDULE_TZ"] = "Europe/Berlin"
        try:
            _, timer = self.install("daily 07:00")
            self.assertIn("Europe/Berlin", timer)
        finally:
            if env_before is None:
                os.environ.pop("AH_SCHEDULE_TZ", None)
            else:
                os.environ["AH_SCHEDULE_TZ"] = env_before
