"""Tests of packages/homenet/install.py: a real run in a subprocess, and the missing and timed-out paths patched."""
from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "packages" / "homenet" / "install.py"


def load_install() -> Any:
    spec = importlib.util.spec_from_file_location("homenet_install_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALL = load_install()


def which_only(found: "dict[str, str]") -> Any:
    return lambda name: found.get(name)


class InstallRunTest(unittest.TestCase):
    def test_real_run_reports_python_and_ssh(self) -> None:
        done = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(done.returncode, 0, f"stderr: {done.stderr!r}")
        self.assertIn("python:", done.stdout)
        self.assertIn("ssh:", done.stdout)
        self.assertIn("ping:", done.stdout)
        self.assertIn(f"{sys.version_info[0]}.{sys.version_info[1]}", done.stdout)

    def test_main_returns_zero_and_prints_the_report(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = INSTALL.main()
        self.assertEqual(code, 0)
        self.assertIn("python:", out.getvalue())


class InstallPathsTest(unittest.TestCase):
    def test_ssh_missing(self) -> None:
        with mock.patch.object(INSTALL.shutil, "which", which_only({})), \
                mock.patch.object(INSTALL.subprocess, "run") as run:
            lines = INSTALL.ssh_lines()
        run.assert_not_called()
        self.assertEqual(len(lines), 1)
        self.assertIn("ssh: not found on PATH", lines[0])

    def test_ssh_version_line(self) -> None:
        fake = subprocess.CompletedProcess(["ssh", "-V"], 0, stdout="", stderr="OpenSSH_9.9p1 Example, 1.0\n")
        with mock.patch.object(INSTALL.shutil, "which", which_only({"ssh": "/usr/bin/ssh"})), \
                mock.patch.object(INSTALL.subprocess, "run", return_value=fake) as run:
            lines = INSTALL.ssh_lines()
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/ssh", "-V"])
        self.assertIn("OpenSSH_9.9p1", lines[0])

    def test_ssh_timed_out_is_not_present_or_missing(self) -> None:
        error = subprocess.TimeoutExpired(["ssh", "-V"], 10)
        with mock.patch.object(INSTALL.shutil, "which", which_only({"ssh": "/usr/bin/ssh"})), \
                mock.patch.object(INSTALL.subprocess, "run", side_effect=error):
            lines = INSTALL.ssh_lines()
        self.assertIn("could not check: timed out", lines[0])
        self.assertNotIn("not found", lines[0])

    def test_ssh_cannot_start(self) -> None:
        with mock.patch.object(INSTALL.shutil, "which", which_only({"ssh": "/usr/bin/ssh"})), \
                mock.patch.object(INSTALL.subprocess, "run", side_effect=PermissionError("denied")):
            lines = INSTALL.ssh_lines()
        self.assertIn("could not check: PermissionError", lines[0])

    def test_ssh_silent_version(self) -> None:
        fake = subprocess.CompletedProcess(["ssh", "-V"], 0, stdout="", stderr="")
        with mock.patch.object(INSTALL.shutil, "which", which_only({"ssh": "/usr/bin/ssh"})), \
                mock.patch.object(INSTALL.subprocess, "run", return_value=fake):
            lines = INSTALL.ssh_lines()
        self.assertIn("printed nothing", lines[0])

    def test_ping_found_and_missing(self) -> None:
        with mock.patch.object(INSTALL.shutil, "which", which_only({"ping": "/bin/ping"})):
            self.assertIn("found at /bin/ping", INSTALL.ping_lines()[0])
        with mock.patch.object(INSTALL.shutil, "which", which_only({})):
            self.assertIn("not found", INSTALL.ping_lines()[0])

    def test_python_too_old(self) -> None:
        self.assertIn("ok", INSTALL.python_lines((3, 9, 0))[0])
        self.assertIn("too old", INSTALL.python_lines((3, 8, 18))[0])

    STUB = r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\python.exe"

    def windows_text(self, found: "dict[str, str]", **run: Any) -> "tuple[str, Any]":
        with mock.patch.object(INSTALL.shutil, "which", which_only(found)), \
                mock.patch.object(INSTALL.subprocess, "run", **run) as called:
            lines = INSTALL.windows_lines()
        return "\n".join(lines), called

    def test_windows_store_stub_and_py(self) -> None:
        fake = subprocess.CompletedProcess([self.STUB], 9009, stdout="", stderr="Python was not found; run without "
                                           "arguments to install from the Microsoft Store\n")
        text, run = self.windows_text({"python": self.STUB, "py": r"C:\Windows\py.exe"}, return_value=fake)
        self.assertIn("python: " + self.STUB + " is the Microsoft Store stub", text)
        self.assertIn("python3: not found", text)
        self.assertIn("py: found at", text)
        self.assertEqual(run.call_args.args[0][:2], [self.STUB, "-c"])
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_windows_alias_that_runs_python(self) -> None:
        fake = subprocess.CompletedProcess([self.STUB], 0, stdout="3.14\n", stderr="")
        text, _ = self.windows_text({"python": self.STUB}, return_value=fake)
        self.assertIn("python: " + self.STUB + " (an app alias that runs Python 3.14)", text)
        self.assertNotIn("Store", text)

    def test_windows_alias_timed_out_is_no_verdict(self) -> None:
        text, _ = self.windows_text({"python": self.STUB}, side_effect=subprocess.TimeoutExpired([self.STUB], 10))
        self.assertIn("could not check: timed out", text)
        self.assertNotIn("Store", text)

    def test_windows_alias_cannot_start(self) -> None:
        text, _ = self.windows_text({"python": self.STUB}, side_effect=PermissionError("denied"))
        self.assertIn("could not check: PermissionError", text)

    def test_windows_installed_python_is_not_started(self) -> None:
        text, run = self.windows_text({"python": r"C:\Python314\python.exe"})
        run.assert_not_called()
        self.assertIn(r"python: C:\Python314\python.exe", text)

    def test_windows_lines_only_on_windows(self) -> None:
        with mock.patch.object(INSTALL.shutil, "which", which_only({})), \
                mock.patch.object(INSTALL.subprocess, "run") as run:
            linux = INSTALL.build_report("linux", (3, 12, 1))
            windows = INSTALL.build_report("win32", (3, 12, 1))
        run.assert_not_called()
        self.assertFalse(any(line.startswith("py:") for line in linux))
        self.assertTrue(any(line.startswith("py:") for line in windows))

    def test_unexpected_error_exits_one_and_names_it(self) -> None:
        err = io.StringIO()
        with mock.patch.object(INSTALL, "build_report", side_effect=RuntimeError("boom")), redirect_stderr(err):
            code = INSTALL.main()
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", err.getvalue())
        self.assertIn("boom", err.getvalue())


if __name__ == "__main__":
    unittest.main()
