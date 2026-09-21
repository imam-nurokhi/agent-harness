"""One schedule string, two renderings, and they must mean the same instant.

`_sv_schedule` is the single parser that turns "daily 07:00" or "hourly :10"
into a launchd StartCalendarInterval and a systemd OnCalendar. A schedule that
rendered to two different times depending on the host is exactly the bug the
supervisor abstraction exists to prevent, so both renderings are pinned here.

This also locks in the daily and weekly forms that task-030 depends on, and
adds the hourly form the auto-resume timer needs.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPERVISE = ROOT / "bin" / "lib" / "supervise.sh"


def _schedule(fmt: str, spec: str) -> str:
    proc = subprocess.run(
        ["bash", "-c",
         f'. "{SUPERVISE}"; _sv_schedule "{fmt}" "{spec}"'],
        capture_output=True, text=True,
        env={"HOME": str(Path.home()), "PATH": "/usr/bin:/bin",
             "WORKSPACE": str(ROOT)})
    return proc.stdout.strip()


class ScheduleTests(unittest.TestCase):
    def test_daily_launchd_has_hour_and_minute(self):
        out = _schedule("launchd", "daily 07:00")
        self.assertIn("<key>Hour</key><integer>7</integer>", out)
        self.assertIn("<key>Minute</key><integer>0</integer>", out)
        self.assertNotIn("Weekday", out)

    def test_daily_systemd(self):
        self.assertEqual(_schedule("systemd", "daily 07:00"), "*-*-* 07:00:00")

    def test_weekly_launchd_has_weekday(self):
        out = _schedule("launchd", "weekly Mon 09:00")
        self.assertIn("<key>Weekday</key><integer>1</integer>", out)
        self.assertIn("<key>Hour</key><integer>9</integer>", out)

    def test_weekly_systemd_has_day(self):
        self.assertEqual(_schedule("systemd", "weekly Mon 09:00"),
                         "Mon *-*-* 09:00:00")

    def test_hourly_launchd_is_minute_only(self):
        """A launchd calendar interval with only a Minute fires every hour."""
        out = _schedule("launchd", "hourly :10")
        self.assertIn("<key>Minute</key><integer>10</integer>", out)
        self.assertNotIn("<key>Hour</key>", out)
        self.assertNotIn("Weekday", out)

    def test_hourly_systemd_wildcards_the_hour(self):
        self.assertEqual(_schedule("systemd", "hourly :10"), "*-*-* *:10:00")

    def test_bare_hourly_defaults_to_the_top_of_the_hour(self):
        out = _schedule("launchd", "hourly")
        self.assertIn("<key>Minute</key><integer>0</integer>", out)
        self.assertNotIn("<key>Hour</key>", out)
        self.assertEqual(_schedule("systemd", "hourly"), "*-*-* *:00:00")


if __name__ == "__main__":
    unittest.main()
