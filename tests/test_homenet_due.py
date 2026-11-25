"""Tests of the script homenet_due: run through main() against status files in temporary folders."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List, Optional, Tuple

MODULE_PATH = (Path(__file__).resolve().parents[1] / "packages" / "homenet" / "post-template" / "scripts"
               / "homenet_due.py")


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("homenet_due_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {MODULE_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


MODULE = load_module()
TODAY = "2026-11-24"


def run(root: Path, *args: str, today: Optional[str] = TODAY) -> Tuple[int, str, str]:
    """Run main() and return (exit code, stdout, stderr)."""
    argv: List[str] = ["--root", str(root)]
    if today is not None:
        argv += ["--today", today]
    argv += list(args)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = MODULE.main(argv)
    return code, out.getvalue(), err.getvalue()


class DueTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.maint = self.root / "docs" / "project" / "homenet" / "maintenance"
        self.maint.mkdir(parents=True)

    def status(self, name: str, *lines: str, raw: Optional[str] = None) -> Path:
        path = self.maint / f"{name}.md"
        text = raw if raw is not None else "---\n" + "\n".join(lines) + "\n---\n\nNotes.\n"
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def test_due_by_date(self) -> None:
        self.status("versions", "interval: 1w", "last: 2026-11-10", "next: 2026-11-24")
        code, out, _ = run(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertTrue(out.startswith("versions"), out)
        self.assertIn("2026-11-24", out)

    def test_overdue_is_due(self) -> None:
        self.status("versions", "interval: 7d", "last: 2026-11-01", "next: 2026-11-08")
        self.assertTrue(run(self.root)[1].startswith("versions"))

    def test_not_due(self) -> None:
        self.status("versions", "interval: 1w", "last: 2026-11-20", "next: 2026-11-25")
        self.assertEqual(run(self.root), (0, "", ""))

    def test_no_directory_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(run(Path(other)), (0, "", ""))

    def test_last_never_is_due(self) -> None:
        self.status("audit", "interval: 4w", "last: never", "next: 2027-01-01")
        code, out, _ = run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("audit"), out)
        self.assertIn("never", out)

    def test_readme_is_ignored(self) -> None:
        (self.maint / "README.md").write_text("no header here\n", encoding="utf-8")
        self.assertEqual(run(self.root, "--check"), (0, "", ""))
        self.assertEqual(run(self.root), (0, "", ""))

    def test_trigger_unchanged_is_not_due(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        digest = self._hash_with_status()
        self.status("devices", "last: 2026-11-20", "next: 2026-12-20", "trigger: docs/project/homenet/devices/*.md",
                    f"trigger-hash: {digest}")
        self.assertEqual(run(self.root), (0, "", ""))

    def test_trigger_changed_is_due(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        digest = self._hash_with_status()
        self.status("devices", "last: 2026-11-20", "next: 2026-12-20", "trigger: docs/project/homenet/devices/*.md",
                    f"trigger-hash: {digest}")
        self.write("docs/project/homenet/devices/a.md", "alpha changed\n")
        code, out, _ = run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("devices"), out)
        self.assertIn("trigger", out)

    def test_trigger_new_file_is_due(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        digest = self._hash_with_status()
        self.status("devices", "last: 2026-11-20", "next: 2026-12-20", "trigger: docs/project/homenet/devices/*.md",
                    f"trigger-hash: {digest}")
        self.write("docs/project/homenet/devices/b.md", "beta\n")
        self.assertTrue(run(self.root)[1].startswith("devices"))

    def _hash_with_status(self) -> str:
        """The trigger hash of the devices glob, taken through --hash from a placeholder status file."""
        self.status("devices", "last: 2026-11-20", "next: 2026-12-20", "trigger: docs/project/homenet/devices/*.md",
                    "trigger-hash: placeholder")
        code, out, _ = run(self.root, "--hash", "devices")
        self.assertEqual(code, 0)
        return out.strip()

    def test_broken_status_file_is_skipped_silently(self) -> None:
        self.status("badfield", "interval: soon", "last: 2026-11-01", "next: 2026-11-02")
        self.status("baddate", "interval: 1w", "last: 2026-11-01", "next: 2026-13-45")
        self.status("missing", "interval: 1w", "last: 2026-11-01")
        self.status("nohead", raw="just text, no header\n")
        (self.maint / "binary.md").write_bytes(b"\xff\xfe\x00bad")
        self.status("good", "interval: 1w", "last: 2026-11-20", "next: 2026-11-30")
        self.assertEqual(run(self.root), (0, "", ""))

    def test_broken_file_does_not_hide_a_due_one(self) -> None:
        self.status("broken", "interval: 1w", "last: x", "next: y")
        self.status("due", "interval: 1w", "last: 2026-11-01", "next: 2026-11-08")
        code, out, _ = run(self.root)
        self.assertEqual(code, 0)
        self.assertEqual([line.split(":")[0] for line in out.splitlines()], ["due"])

    def test_more_than_five_due(self) -> None:
        for index in range(7):
            self.status(f"task{index}", "interval: 1w", "last: 2026-11-01", "next: 2026-11-08")
        code, out, _ = run(self.root)
        lines = out.splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[-1], "… +3 more")
        self.assertTrue(all(line.startswith("task") for line in lines[:4]))

    def test_exactly_five_due_are_all_listed(self) -> None:
        for index in range(5):
            self.status(f"task{index}", "interval: 1w", "last: 2026-11-01", "next: 2026-11-08")
        lines = run(self.root)[1].splitlines()
        self.assertEqual(len(lines), 5)
        self.assertFalse(any("more" in line for line in lines))

    def test_check_names_the_broken_file(self) -> None:
        self.status("badfield", "interval: soon", "last: 2026-11-01", "next: 2026-11-02")
        self.status("baddate", "interval: 1w", "last: 2026-11-01", "next: 2026-13-45")
        self.status("good", "interval: 1w", "last: 2026-11-20", "next: 2026-11-30")
        code, out, err = run(self.root, "--check")
        self.assertEqual(code, 1)
        self.assertIn("badfield.md", out + err)
        self.assertIn("soon", out + err)
        self.assertIn("baddate.md", out + err)
        self.assertIn("2026-13-45", out + err)
        self.assertNotIn("good.md", out + err)

    def test_check_clean_is_silent(self) -> None:
        self.status("good", "interval: 1w", "last: 2026-11-20", "next: 2026-11-30")
        self.assertEqual(run(self.root, "--check"), (0, "", ""))

    def test_hash_is_stable_across_a_run(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        self.write("docs/project/homenet/devices/b.md", "beta\n")
        self.status("devices", "last: never", "next: 2026-12-20", "trigger: docs/project/homenet/devices/*.md",
                    "trigger-hash: placeholder")
        before = run(self.root, "--hash", "devices")
        run(self.root)
        after = run(self.root, "--hash", "devices")
        self.assertEqual(before[0], 0)
        self.assertEqual(before, after)
        self.assertRegex(before[1].strip(), r"^[0-9a-f]{64}$")

    def test_hash_changes_with_content(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        self.status("devices", "last: never", "next: 2026-12-20", "trigger: docs/project/homenet/devices/*.md",
                    "trigger-hash: x")
        before = run(self.root, "--hash", "devices")[1]
        self.write("docs/project/homenet/devices/a.md", "alpha!\n")
        self.assertNotEqual(before, run(self.root, "--hash", "devices")[1])

    def test_hash_without_trigger_or_unknown_task(self) -> None:
        self.status("versions", "interval: 1w", "last: 2026-11-20", "next: 2026-11-30")
        code, out, err = run(self.root, "--hash", "versions")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("versions", err)
        code, out, err = run(self.root, "--hash", "nothing")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("nothing", err)

    def test_unexpected_error_still_exits_zero_without_traceback(self) -> None:
        original = MODULE.load_statuses

        def boom(root: Path) -> Any:
            raise RuntimeError("boom")

        MODULE.load_statuses = boom
        try:
            code, out, err = run(self.root)
        finally:
            MODULE.load_statuses = original
        self.assertEqual((code, out, err), (0, "", ""))

    GLOB = "trigger: docs/project/homenet/devices/*.md"

    def _devices_hash(self) -> str:
        return self._hash_with_status()

    def test_trigger_only_without_next_unchanged_is_not_due(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        digest = self._devices_hash()
        self.status("devices", "last: 2026-11-20", self.GLOB, f"trigger-hash: {digest}")
        self.assertEqual(run(self.root), (0, "", ""))
        self.assertEqual(run(self.root, "--check"), (0, "", ""))

    def test_trigger_only_without_next_changed_is_due(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        digest = self._devices_hash()
        self.status("devices", "last: 2026-11-20", self.GLOB, f"trigger-hash: {digest}")
        self.write("docs/project/homenet/devices/a.md", "alpha changed\n")
        self.assertTrue(run(self.root)[1].startswith("devices"))

    def test_trigger_only_with_next_today_is_due(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        digest = self._devices_hash()
        self.status("devices", "last: 2026-11-20", "next: 2026-11-20", self.GLOB, f"trigger-hash: {digest}")
        code, out, _ = run(self.root)
        self.assertEqual(code, 0)
        self.assertIn("due since 2026-11-20", out)

    def test_trigger_hash_none_is_due(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        self.status("devices", "last: 2026-11-20", self.GLOB, "trigger-hash: none")
        self.assertTrue(run(self.root)[1].startswith("devices"))
        self.assertEqual(run(self.root, "--check"), (0, "", ""))

    def test_interval_without_next_is_broken(self) -> None:
        self.status("versions", "interval: 1w", "last: 2026-11-20")
        code, out, err = run(self.root, "--check")
        self.assertEqual(code, 1)
        self.assertIn("next", out + err)

    def test_failing_trigger_hash_does_not_hide_other_tasks(self) -> None:
        self.status("aaa", "last: 2026-11-20", "trigger: docs/x/*.md", "trigger-hash: none")
        self.status("zzz", "interval: 1w", "last: 2026-11-01", "next: 2026-11-08")
        original = MODULE.trigger_hash

        def raising(root: Path, pattern: str) -> str:
            raise ValueError("Invalid pattern: '**' can only be an entire path component")

        MODULE.trigger_hash = raising
        try:
            code, out, err = run(self.root)
            self.assertEqual((code, err), (0, ""))
            self.assertEqual([line.split(":")[0] for line in out.splitlines()], ["zzz"])
            code, out, err = run(self.root, "--check")
        finally:
            MODULE.trigger_hash = original
        self.assertEqual(code, 1)
        self.assertIn("aaa.md", out + err)
        self.assertIn("Invalid pattern", out + err)
        self.assertNotIn("zzz.md", out + err)

    def test_bad_trigger_globs_are_broken(self) -> None:
        for glob in ("/etc/*.md", "C:/x/*.md", "C:\\x\\*.md", "/x/*.md", "../x", "docs/../x/*.md", "docs/**.md"):
            with self.subTest(glob=glob):
                self.status("bad", "last: 2026-11-20", f"trigger: {glob}", "trigger-hash: none")
                code, out, err = run(self.root, "--check")
                self.assertEqual(code, 1)
                self.assertIn("bad.md", out + err)
                self.assertIn("trigger", out + err)
                self.assertEqual(run(self.root), (0, "", ""))

    def test_whole_component_double_star_is_valid(self) -> None:
        self.status("ok", "last: 2026-11-20", "trigger: docs/**/*.md", "trigger-hash: none")
        self.assertEqual(run(self.root, "--check"), (0, "", ""))

    def test_maintenance_files_never_count_for_the_hash(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        glob = "trigger: docs/project/homenet/**/*.md"
        self.status("devices", "last: 2026-11-20", glob, "trigger-hash: placeholder")
        digest = run(self.root, "--hash", "devices")[1].strip()
        self.status("devices", "last: 2026-11-20", glob, f"trigger-hash: {digest}")
        self.assertEqual(run(self.root), (0, "", ""))
        self.write("docs/project/homenet/maintenance/report-2026.md", "a report\n")
        self.status("other", "interval: 1w", "last: 2026-11-20", "next: 2026-11-30")
        self.assertEqual(run(self.root), (0, "", ""))
        self.write("docs/project/homenet/devices/a.md", "alpha changed\n")
        self.assertTrue(run(self.root)[1].startswith("devices"))

    def test_file_resolving_outside_the_root_is_not_hashed(self) -> None:
        self.write("docs/project/homenet/devices/a.md", "alpha\n")
        self.status("devices", "last: 2026-11-20", self.GLOB, "trigger-hash: x")
        alone = run(self.root, "--hash", "devices")[1]
        self.write("docs/project/homenet/devices/b.md", "beta\n")
        self.assertNotEqual(alone, run(self.root, "--hash", "devices")[1])
        outside = Path(self._tmp.name).parent / "elsewhere" / "b.md"
        original = MODULE.resolve_path

        def fake(path: Path) -> Path:
            return outside if path.name == "b.md" else original(path)

        MODULE.resolve_path = fake
        try:
            self.assertEqual(alone, run(self.root, "--hash", "devices")[1])
        finally:
            MODULE.resolve_path = original

    def test_bad_today_in_default_mode_is_silent(self) -> None:
        self.status("versions", "interval: 1w", "last: 2026-11-01", "next: 2026-11-08")
        self.assertEqual(run(self.root, today="2026-13-01"), (0, "", ""))

    def test_bad_today_with_check_or_hash_fails(self) -> None:
        self.status("versions", "interval: 1w", "last: 2026-11-01", "next: 2026-11-08")
        for flag in (["--check"], ["--hash", "versions"]):
            with self.subTest(flag=flag):
                code, out, err = run(self.root, *flag, today="2026-13-01")
                self.assertEqual((code, out), (1, ""))
                self.assertIn("2026-13-01", err)

    def test_module_has_no_ticket_ids(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\b(T\d{2,}|B\d{2,}|Q\d+|U\d+|ADR-\d+)\b")


if __name__ == "__main__":
    unittest.main()
