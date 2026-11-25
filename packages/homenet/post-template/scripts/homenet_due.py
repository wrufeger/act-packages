#!/usr/bin/env python3
"""List the homenet maintenance tasks that are due.

Reads the status files `docs/project/homenet/maintenance/<task>.md` (every `*.md` except `README.md`). Each starts
with a header block between `---` lines:

    interval:     <n>d or <n>w (absent for a task that only has a trigger)
    last:         YYYY-MM-DD or never
    next:         YYYY-MM-DD (required with `interval`, optional without)
    trigger:      glob relative to the project root (optional)
    trigger-hash: SHA-256 stored after the last run, or `none` for a new task (required with a trigger)

A task is due when `next` is set and is today or earlier, when `last` is `never`, or when the hash over the
trigger files differs from `trigger-hash`. The status files and reports under the maintenance folder never count
for the hash, nor does a file that resolves outside the project root.

Usage:
    homenet_due.py [--root DIR] [--today YYYY-MM-DD]     one line per due task, nothing when none is due
    homenet_due.py --check                               name every broken status file (exit 1 if any)
    homenet_due.py --hash TASK                           print the current trigger hash of TASK

The default mode always exits 0 and never prints a traceback. Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, List, Optional, Sequence, Tuple, Union

MAINTENANCE_DIR = Path("docs") / "project" / "homenet" / "maintenance"
MAX_LINES = 5
INTERVAL_RE = re.compile(r"^[1-9][0-9]*[dw]$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


@dataclass(frozen=True)
class Status:
    """A parsed status file."""

    name: str
    interval: Optional[str]
    last: Optional[datetime.date]  # None means `never`
    next_date: Optional[datetime.date]
    trigger: Optional[str]
    trigger_hash: Optional[str]


@dataclass(frozen=True)
class Broken:
    """A status file that cannot be used, with what is wrong."""

    name: str
    problem: str


def parse_date(field: str, value: str) -> datetime.date:
    """Parse `YYYY-MM-DD` strictly; raise ValueError naming the field and the value."""
    if not DATE_RE.match(value):
        raise ValueError(f"{field}: bad date {value!r}, expected YYYY-MM-DD")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field}: bad date {value!r}, not a calendar date") from None


def read_header(text: str) -> Dict[str, str]:
    """Return the `key: value` pairs of the block between the first two `---` lines."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("header: file does not start with a --- line")
    fields: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip():
            raise ValueError(f"header: malformed line {line.strip()!r}")
        fields[key.strip()] = value.strip()
    raise ValueError("header: closing --- line is missing")


def check_trigger(trigger: str) -> None:
    """Raise ValueError unless the glob stays relative to the project root and is valid on every Python."""
    for flavour in (PurePosixPath, PureWindowsPath):
        parts = flavour(trigger)
        if parts.is_absolute() or parts.anchor or parts.drive:
            raise ValueError(f"trigger: {trigger!r} must be a glob relative to the project root")
        if ".." in parts.parts:
            raise ValueError(f"trigger: {trigger!r} must not contain '..'")
        if any("**" in part and part != "**" for part in parts.parts):
            raise ValueError(f"trigger: {trigger!r} uses '**' other than as a whole path component")


def parse_status(path: Path) -> Union[Status, Broken]:
    """Parse one status file; a problem is returned as Broken, never raised."""
    name = path.stem
    try:
        fields = read_header(path.read_text(encoding="utf-8"))
        if "last" not in fields:
            raise ValueError("last: field is missing")
        interval = fields.get("interval") or None
        if "interval" in fields and "next" not in fields:
            raise ValueError("next: field is missing (required with interval)")
        if "interval" in fields and (interval is None or not INTERVAL_RE.match(interval)):
            raise ValueError(f"interval: bad value {fields['interval']!r}, expected <n>d or <n>w")
        trigger = fields.get("trigger") or None
        if "trigger" in fields and trigger is None:
            raise ValueError("trigger: field is empty")
        if trigger is not None:
            check_trigger(trigger)
            if "trigger-hash" not in fields:
                raise ValueError("trigger-hash: field is missing")
        if interval is None and trigger is None:
            raise ValueError("interval: field is missing and there is no trigger")
        last = None if fields["last"] == "never" else parse_date("last", fields["last"])
        next_date = parse_date("next", fields["next"]) if "next" in fields else None
        return Status(name, interval, last, next_date, trigger, fields.get("trigger-hash") if trigger else None)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return Broken(name, str(error))


def load_statuses(root: Path) -> Tuple[List[Status], List[Broken]]:
    """Parse every status file of the project, sorted by task name."""
    good: List[Status] = []
    bad: List[Broken] = []
    directory = root / MAINTENANCE_DIR
    if not directory.is_dir():
        return good, bad
    for path in sorted(directory.glob("*.md")):
        if path.name == "README.md" or not path.is_file():
            continue
        parsed = parse_status(path)
        if isinstance(parsed, Status):
            good.append(parsed)
        else:
            bad.append(parsed)
    return good, bad


def resolve_path(path: Path) -> Path:
    """The real path of `path` (a seam for the tests of the containment check)."""
    return path.resolve()


def counts_for_hash(root_real: Path, path: Path) -> bool:
    """True for a file inside the root that is not a status file or report of the maintenance folder."""
    try:
        relative = resolve_path(path).relative_to(root_real)
    except ValueError:
        return False
    return relative.parts[: len(MAINTENANCE_DIR.parts)] != MAINTENANCE_DIR.parts


def trigger_hash(root: Path, pattern: str) -> str:
    """SHA-256 over the sorted relative paths and the contents of the files the glob matches."""
    digest = hashlib.sha256()
    root_real = resolve_path(root)
    files = sorted(p for p in root.glob(pattern) if p.is_file() and counts_for_hash(root_real, p))
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def reasons(status: Status, root: Path, today: datetime.date) -> List[str]:
    """Why the task is due; an empty list means it is not."""
    found: List[str] = []
    if status.last is None:
        found.append("never run")
    if status.next_date is not None and status.next_date <= today:
        found.append(f"due since {status.next_date.isoformat()}")
    if status.trigger is not None and trigger_hash(root, status.trigger) != status.trigger_hash:
        found.append(f"trigger files changed ({status.trigger})")
    return found


def due_lines(root: Path, today: datetime.date) -> List[str]:
    """One `<task>: <reasons>` line per due task."""
    good, _ = load_statuses(root)
    lines: List[str] = []
    for status in good:
        try:
            why = reasons(status, root, today)
        except (OSError, ValueError, NotImplementedError):
            continue  # a trigger that cannot be hashed: this task gives no line, the others still print
        if why:
            lines.append(f"{status.name}: {'; '.join(why)}")
    return lines


def cap(lines: List[str]) -> List[str]:
    """At most MAX_LINES lines; with more, MAX_LINES - 1 and a count of the rest."""
    if len(lines) <= MAX_LINES:
        return lines
    return lines[: MAX_LINES - 1] + [f"… +{len(lines) - (MAX_LINES - 1)} more"]


def run_default(root: Path, today: datetime.date) -> int:
    """Default mode: print what is due, exit 0 whatever happens."""
    try:
        lines = cap(due_lines(root, today))
        if lines:
            print("\n".join(lines))
    except Exception:  # noqa: BLE001 - by design: this mode never fails a session start
        return 0
    return 0


def run_check(root: Path) -> int:
    """--check: name every broken status file and every trigger that cannot be hashed; exit 1 if any."""
    good, bad = load_statuses(root)
    problems = [(item.name, item.problem) for item in bad]
    for status in good:
        if status.trigger is None:
            continue
        try:
            trigger_hash(root, status.trigger)
        except (OSError, ValueError, NotImplementedError) as error:
            problems.append((status.name, f"trigger: cannot hash {status.trigger!r}: {error}"))
    for name, problem in sorted(problems):
        print(f"{name}.md: {problem}")
    return 1 if problems else 0


def run_hash(root: Path, task: str) -> int:
    """--hash: print the current trigger hash of a task."""
    good, bad = load_statuses(root)
    for status in good:
        if status.name == task:
            if status.trigger is None:
                print(f"homenet_due: task {task!r} has no trigger", file=sys.stderr)
                return 1
            print(trigger_hash(root, status.trigger))
            return 0
    broken = next((b for b in bad if b.name == task), None)
    detail = f" (status file is broken: {broken.problem})" if broken else " (no such status file)"
    print(f"homenet_due: cannot hash task {task!r}{detail}", file=sys.stderr)
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="List the homenet maintenance tasks that are due.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--today", help="date to compare with, YYYY-MM-DD (default: today)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="name broken status files, exit 1 if any")
    mode.add_argument("--hash", metavar="TASK", help="print the current trigger hash of TASK")
    args = parser.parse_args(argv)
    try:
        root = Path(args.root)
        try:
            today = parse_date("--today", args.today) if args.today else datetime.date.today()
        except ValueError as error:
            if args.check or args.hash:
                print(f"homenet_due: {error}", file=sys.stderr)
                return 1
            return 0  # default mode never fails a session start
        if args.check:
            return run_check(root)
        if args.hash:
            return run_hash(root, args.hash)
        return run_default(root, today)
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - report without a traceback
        print(f"homenet_due: {type(error).__name__}: {error}", file=sys.stderr)
        return 1 if (args.check or args.hash) else 0


if __name__ == "__main__":
    sys.exit(main())
