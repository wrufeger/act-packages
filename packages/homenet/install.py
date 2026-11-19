#!/usr/bin/env python3
"""Setup report of the package `homenet`: which tools are there. It only reports.

It opens no network connection, writes no file and never touches `~/.ssh`. The programs it starts, each with a
time limit, are `ssh -V` (a version line) and, on Windows, a `python` or `python3` app alias with `-c` (it prints
its version). Output goes to stdout, exit code 0; an unexpected error exits 1 with a message that names what
failed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from typing import List

SUBPROCESS_LIMIT = 10  # seconds a started program may take
MIN_PYTHON = (3, 9)
VERSION_CODE = "import sys; print(*sys.version_info[:2], sep='.')"
VERSION_RE = re.compile(r"\d+\.\d+")


def python_lines(version: tuple) -> List[str]:
    """The Python version and whether it is new enough."""
    text = ".".join(str(part) for part in version[:3])
    need = ".".join(str(part) for part in MIN_PYTHON)
    if tuple(version[:2]) >= MIN_PYTHON:
        return [f"python: {text} (needs {need} or newer: ok)"]
    return [f"python: {text} (needs {need} or newer: too old, the package code may not run)"]


def ssh_lines() -> List[str]:
    """`ssh` on PATH and its `ssh -V` line."""
    path = shutil.which("ssh")
    if path is None:
        return ["ssh: not found on PATH (needed for SSH access to hosts; install an OpenSSH client)"]
    try:
        # `ssh -V` prints its version line to stderr; it connects nowhere
        done = subprocess.run([path, "-V"], capture_output=True, text=True, errors="replace",
                              timeout=SUBPROCESS_LIMIT, check=False)
    except subprocess.TimeoutExpired:
        return [f"ssh: found at {path}; could not check: timed out after {SUBPROCESS_LIMIT} s"]
    except OSError as error:
        return [f"ssh: found at {path}; could not check: {type(error).__name__}: {error}"]
    version = (done.stderr or done.stdout).strip().splitlines()
    return [f"ssh: found at {path}; {version[0] if version else 'ssh -V printed nothing'}"]


def ping_lines() -> List[str]:
    """`ping` on PATH (only looked up, never run)."""
    path = shutil.which("ping")
    return [f"ping: found at {path}"] if path else ["ping: not found on PATH"]


def alias_line(name: str, path: str) -> str:
    """An app alias under `WindowsApps` either runs an installed Python or is the Store stub; started to tell them
    apart. With arguments the stub prints a hint and fails; it does not open the Store."""
    try:
        done = subprocess.run([path, "-c", VERSION_CODE], capture_output=True, text=True, errors="replace",
                              stdin=subprocess.DEVNULL, timeout=SUBPROCESS_LIMIT, check=False)
    except subprocess.TimeoutExpired:
        return f"{name}: {path} is an app alias; could not check: timed out after {SUBPROCESS_LIMIT} s"
    except OSError as error:
        return f"{name}: {path} is an app alias; could not check: {type(error).__name__}: {error}"
    version = done.stdout.strip()
    if done.returncode == 0 and VERSION_RE.fullmatch(version):
        return f"{name}: {path} (an app alias that runs Python {version})"
    return f"{name}: {path} is the Microsoft Store stub (it runs no Python; use `py -3` or an installed Python)"


def windows_lines() -> List[str]:
    """On Windows: what `python` and `python3` are (an app alias is started once), and whether `py` exists."""
    lines = []
    for name in ("python", "python3"):
        path = shutil.which(name)
        if path is None:
            lines.append(f"{name}: not found on PATH")
        elif "\\windowsapps\\" in path.lower():
            lines.append(alias_line(name, path))
        else:
            lines.append(f"{name}: {path}")
    path = shutil.which("py")
    lines.append(f"py: found at {path}" if path else "py: not found on PATH")
    return lines


def build_report(platform: str, version: tuple) -> List[str]:
    """The report lines for this machine."""
    lines = ["homenet: tools on this machine (a report only; nothing was changed, no connection was opened)"]
    lines += python_lines(version)
    lines += ssh_lines()
    lines += ping_lines()
    if platform == "win32":
        lines += windows_lines()
    return lines


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")  # a path with a character the console cannot show
    except AttributeError:
        pass
    try:
        report = build_report(sys.platform, tuple(sys.version_info[:3]))
    except Exception as error:  # reported with its class, never silent
        print(f"homenet install.py failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
