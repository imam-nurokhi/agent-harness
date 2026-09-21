"""A trigger that was never installed cannot be late.

Seen 2026-09-21 alongside the auto-resume spam:

    ⏰ Trigger sweep terlambat — jadwal weekly Sun 20:00, seharusnya jalan
    2026-09-20 20:00. Terakhir jalan: 2026-09-13 21:07

`sweep` is one of three triggers the owner deliberately left uninstalled
(CLAUDE.md §7) because each one spends engine quota. Telling someone that a
schedule they chose not to install did not run is not a warning; it is noise
they cannot act on, and it arrives every week forever.

Underneath sat a second defect of the same family as the 2026-09-17 scheduler
bug: `state` decided "installed" by looking for a **launchd plist**, which on
this Linux host never exists. So every trigger read as uninstalled — including
`standup`, which has a live systemd timer and a `last_run` from this morning.
The installer learned about systemd back then; the status reader never did.
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))


class InstalledDetectionTests(unittest.TestCase):
    """`installed` must answer for the platform the harness is actually on."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.home = Path(self.tmp.name)
        (self.home / "agents").mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in ("AH_WORKSPACE", "XDG_CONFIG_HOME")}
        os.environ["AH_WORKSPACE"] = str(self.home)
        os.environ["XDG_CONFIG_HOME"] = str(self.home / ".config")
        sys.modules.pop("state", None)
        self.state = importlib.import_module("state")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()
        sys.modules.pop("state", None)

    def _systemd_timer(self, tid: str) -> None:
        unit = self.home / ".config" / "systemd" / "user"
        unit.mkdir(parents=True, exist_ok=True)
        (unit / f"com.ah.trigger.{tid}.timer").write_text("[Timer]\n")

    def test_a_systemd_timer_counts_as_installed(self):
        self._systemd_timer("standup")
        self.assertTrue(self.state._trigger_installed("standup"))

    def test_no_unit_anywhere_is_not_installed(self):
        self.assertFalse(self.state._trigger_installed("sweep"))

    def test_an_empty_id_is_not_installed(self):
        self.assertFalse(self.state._trigger_installed(""))

    def test_one_trigger_does_not_vouch_for_another(self):
        self._systemd_timer("standup")
        self.assertFalse(self.state._trigger_installed("sweep"))

    def test_the_unit_directory_follows_xdg_config_home(self):
        # supervise.sh writes units to $XDG_CONFIG_HOME/systemd/user; reading
        # from a hardcoded ~/.config is how the two halves drifted apart.
        moved = self.home / "elsewhere"
        os.environ["XDG_CONFIG_HOME"] = str(moved)
        unit = moved / "systemd" / "user"
        unit.mkdir(parents=True)
        (unit / "com.ah.trigger.standup.timer").write_text("[Timer]\n")
        self.assertTrue(self.state._trigger_installed("standup"))


class OverdueAlertTests(unittest.TestCase):
    """The Telegram-facing half: an uninstalled trigger raises nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.tmp.name)
        for sub in ("tasks", "reports", "roles"):
            (self.workspace / "agents" / sub).mkdir(parents=True)
        (self.workspace / "worktrees").mkdir()
        self.saved = {k: os.environ.get(k) for k in ("AH_WORKSPACE", "XDG_CONFIG_HOME")}
        os.environ["AH_WORKSPACE"] = str(self.workspace)
        os.environ["XDG_CONFIG_HOME"] = str(self.workspace / ".config")
        for name in ("state", "trigmem", "tgcore", "tgcmd", "tgtask", "tgwatch", "jobs"):
            sys.modules.pop(name, None)
        self.state = importlib.import_module("state")
        self.tgwatch = importlib.import_module("tgwatch")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()
        for name in ("state", "trigmem", "tgwatch"):
            sys.modules.pop(name, None)

    def _trigger(self, tid="sweep", last_run="2026-09-13 21:07") -> None:
        import json
        (self.workspace / "agents" / "triggers.json").write_text(json.dumps({
            "triggers": [{"id": tid, "role": "lead", "label": "Stale worktree sweep",
                          "schedule": "weekly Sun 20:00", "last_run": last_run,
                          "prompt": "x"}]
        }))

    def _install(self, tid: str) -> None:
        unit = self.workspace / ".config" / "systemd" / "user"
        unit.mkdir(parents=True, exist_ok=True)
        (unit / f"com.ah.trigger.{tid}.timer").write_text("[Timer]\n")

    def _late_alerts(self):
        # {"triggers": {}} is an already-primed watch file, so events are
        # reported rather than swallowed as first sight.
        return [e for e in self.tgwatch._trigger_events({"triggers": {}})
                if "terlambat" in e]

    def test_an_uninstalled_overdue_trigger_raises_no_alert(self):
        self._trigger()
        self.assertEqual(self._late_alerts(), [],
                         "a trigger that cannot run cannot be late")

    def test_an_installed_overdue_trigger_still_alerts(self):
        # The guard must not silence the alert that matters.
        self._trigger()
        self._install("sweep")
        alerts = self._late_alerts()
        self.assertEqual(len(alerts), 1, "an installed schedule that missed must speak")
        self.assertIn("sweep", alerts[0])

    def test_an_installed_trigger_that_ran_on_time_is_quiet(self):
        import datetime as dt
        recent = (dt.datetime.now() - dt.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        self._trigger(last_run=recent)
        self._install("sweep")
        self.assertEqual(self._late_alerts(), [])


if __name__ == "__main__":
    unittest.main()
