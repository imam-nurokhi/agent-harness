"""Every source file must at least parse, and every module must import.

This exists because it was missed once. `dash.py` was committed with a broken
indent and the whole suite stayed green, because no test had ever imported it:
the dashboard is exercised over HTTP or not at all. The harness then started,
served nothing, and the only evidence was a traceback in a log nobody was
watching.

These are the cheapest tests in the suite and they guard the entry points the
operator actually touches — the dashboard, the bot, and the `ah` CLI.
"""
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "bin" / "lib"

# Modules that are safe to import in a test process: no server socket, no poll
# loop, no launchd. The rest are covered by the compile check below.
IMPORTABLE = ("state", "operations", "engine", "jobs", "scope", "trigmem",
              "tgcore", "tgwatch", "tgtask", "tgcmd")


class SourcesLoadTests(unittest.TestCase):
    def test_every_python_file_compiles(self):
        for path in sorted(LIB.glob("*.py")):
            with self.subTest(file=path.name):
                try:
                    py_compile.compile(str(path), doraise=True)
                except py_compile.PyCompileError as exc:
                    self.fail(f"{path.name} does not compile: {exc}")

    def test_every_shell_file_parses(self):
        targets = sorted(LIB.glob("*.sh")) + [ROOT / "bin" / "ah"]
        for path in targets:
            with self.subTest(file=path.name):
                proc = subprocess.run(["bash", "-n", str(path)],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0,
                                 f"{path.name} does not parse: {proc.stderr}")

    def test_the_operator_facing_modules_import(self):
        """Compiling is not enough: a bad import lands at run time, not parse time."""
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            for name in IMPORTABLE:
                with self.subTest(module=name):
                    proc = subprocess.run(
                        [sys.executable, "-c",
                         f"import sys; sys.path.insert(0, {str(LIB)!r}); import {name}"],
                        capture_output=True, text=True,
                        env={"AH_WORKSPACE": tmp, "PATH": "/usr/bin:/bin",
                             "HOME": str(Path.home())},
                    )
                    self.assertEqual(proc.returncode, 0,
                                     f"import {name} failed: {proc.stderr}")

    def test_the_dashboard_module_imports(self):
        """dash.py binds no port at import time; this is the check it was missing."""
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            proc = subprocess.run(
                [sys.executable, "-c",
                 f"import sys; sys.path.insert(0, {str(LIB)!r}); import dash"],
                capture_output=True, text=True,
                env={"AH_WORKSPACE": tmp, "PATH": "/usr/bin:/bin",
                     "HOME": str(Path.home())},
            )
            self.assertEqual(proc.returncode, 0,
                             f"import dash failed: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
