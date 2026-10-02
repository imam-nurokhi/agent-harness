"""`systemctl --user` needs a bus address, and without one it lies by omission.

`ah trigger list` printed INSTALLED=no for every trigger on 2026-09-21,
including `standup`, which has an enabled systemd timer and had run that
morning. The check itself was right; its environment was not. `systemctl
--user` cannot reach the user manager unless XDG_RUNTIME_DIR points at
/run/user/<uid>, and when it cannot it exits non-zero — which
`sv_is_managed` read as "not installed" rather than "could not ask".

CLAUDE.md §2 already tells a human to export that variable before running
`systemctl --user` here. Code that calls it should not need the reminder, so
supervise.sh now supplies the default itself.
"""
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPERVISE = ROOT / "bin" / "lib" / "supervise.sh"


def _run(snippet: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin", "WORKSPACE": str(ROOT)}
    env.update(env_extra or {})
    return subprocess.run(["bash", "-c", f'. "{SUPERVISE}"; {snippet}'],
                          capture_output=True, text=True, env=env)


class UserBusTests(unittest.TestCase):
    def test_a_default_runtime_dir_is_supplied_when_missing(self):
        out = _run('_sv_user_bus; printf "%s" "$XDG_RUNTIME_DIR"').stdout.strip()
        self.assertEqual(out, f"/run/user/{os.getuid()}")

    def test_an_existing_runtime_dir_is_left_alone(self):
        # A caller that already knows better — a login session, or the units
        # themselves — must not be overridden.
        out = _run('_sv_user_bus; printf "%s" "$XDG_RUNTIME_DIR"',
                   {"XDG_RUNTIME_DIR": "/run/user/9999"}).stdout.strip()
        self.assertEqual(out, "/run/user/9999")

    def test_is_managed_asks_through_the_bus_helper(self):
        # The regression guard: whichever branch runs, the helper must be
        # called before systemctl, or the bug returns silently.
        text = SUPERVISE.read_text()
        body = text.split("sv_is_managed()", 1)[1].split("\n}", 1)[0]
        self.assertIn("_sv_user_bus", body)

    def test_is_managed_is_falsy_for_a_label_that_does_not_exist(self):
        proc = _run('sv_is_managed "com.ah.trigger.definitely-not-installed"')
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
