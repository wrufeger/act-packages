"""Tests of the check module homenet_no_scan: called with payload dicts; no command is ever run."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import shlex
import time
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

MODULE_PATH = (Path(__file__).resolve().parents[1] / "packages" / "homenet" / "post-template" / "hooks" / "checks"
               / "homenet_no_scan.py")


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("homenet_no_scan_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {MODULE_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()

# (tool, command, refused)
BASH_CASES = [
    # refused: scanners, also with a path or .exe
    ("Bash", "nmap host.example", True),
    ("Bash", "nmap -sS 192.0.2.0/24", True),
    ("Bash", "sudo nmap -sS 192.0.2.0/24", True),
    ("Bash", "FOO=1 nmap host.example", True),
    ("Bash", "/usr/bin/nmap host.example", True),
    ("Bash", "nmap.exe host.example", True),
    ("Bash", r'"C:\Tools\nmap.exe" host.example', True),  # quoted, as bash needs it for a Windows path
    ("Bash", "C:/Tools/nmap.exe host.example", True),
    ("Bash", "NMAP host.example", True),
    ("Bash", "masscan 192.0.2.0/24 -p80", True),
    ("Bash", "zmap -p 22 192.0.2.0/24", True),
    ("Bash", "rustscan -a host.example", True),
    ("Bash", "naabu -host host.example", True),
    ("Bash", "unicornscan 198.51.100.7", True),
    ("Bash", "/opt/tools/unicornscan 198.51.100.7", True),
    ('Bash', 'n"m"ap host.example', True),
    ("Bash", "'nmap' host.example", True),
    # refused: after other commands, prefixes and substitutions
    ("Bash", "echo x && masscan 192.0.2.0/24 -p80", True),
    ("Bash", "echo x; nmap host.example", True),
    ("Bash", "echo x || nmap host.example", True),
    ("Bash", "echo x | nmap host.example", True),
    ("Bash", "echo x & nmap host.example", True),
    ("Bash", "echo x\nnmap host.example", True),
    ("Bash", "(nmap host.example)", True),
    ("Bash", "echo $(nmap host.example)", True),
    ("Bash", 'echo "$(nmap host.example)"', True),
    ("Bash", "echo `nmap host.example`", True),
    ("Bash", "timeout 5 rustscan -a host.example", True),
    ("Bash", "timeout -s KILL 5 nmap host.example", True),
    ("Bash", "sudo -u root nmap host.example", True),
    ("Bash", "doas nmap host.example", True),
    ("Bash", "env -i FOO=1 nmap host.example", True),
    ("Bash", "nice -n 5 nmap host.example", True),
    ("Bash", "nohup nmap host.example", True),
    ("Bash", "time nmap host.example", True),
    ("Bash", "command nmap host.example", True),
    ("Bash", "exec nmap host.example", True),
    ("Bash", "echo host.example | xargs -n 1 nmap", True),
    ("Bash", "watch -n 5 nmap host.example", True),
    ("Bash", "nmap host.example > out.txt", True),
    ("Bash", "nmap host.example 2>&1", True),
    ("Bash", "cat < in.txt && nmap host.example", True),
    # refused: remote commands and shell strings
    ("Bash", "ssh pi.example 'nmap 192.0.2.0/24'", True),
    ("Bash", "ssh -o StrictHostKeyChecking=accept-new -p 2222 pi.example \"uptime; nmap 192.0.2.0/24\"", True),
    ("Bash", "ssh pi.example sudo nmap 192.0.2.0/24", True),
    ("Bash", 'bash -c "zmap -p 22 192.0.2.0/24"', True),
    ("Bash", "sh -c 'nmap host.example'", True),
    ("Bash", "bash -lc 'nmap host.example'", True),
    ("Bash", "eval 'nmap host.example'", True),
    ("Bash", "echo ok; bash -c 'echo a; masscan 192.0.2.0/24'", True),
    # refused: netcat sweeps
    ("Bash", "nc -z host.example 20-80", True),
    ("Bash", "nc -zv host.example 22 80", True),
    ("Bash", "nc -vz host.example 22 80 443", True),
    ("Bash", "ncat -z host.example 1-1024", True),
    ("Bash", "netcat -z host.example 22 80", True),
    ("Bash", "nc.exe -z host.example 22 80", True),
    ("Bash", "nc -z -w 2 host.example 22 80", True),
    ("Bash", "ssh pi.example 'nc -z nas.example 1-100'", True),
    # refused: quoting that cannot be parsed falls back to whitespace splitting
    ("Bash", "nmap 'host", True),
    ("Bash", 'echo "x; nmap host', True),
    # passes: the brief's examples
    ("Bash", "ssh host.example 'uptime'", False),
    ("Bash", "ping -c 1 host.example", False),
    ("Bash", "nc -z host.example 22", False),
    ("Bash", "grep nmap notes.md", False),
    ("Bash", "man nmap", False),
    ("Bash", "which nmap", False),
    ("Bash", 'git commit -m "no nmap"', False),
    ("Bash", 'echo "nmap"', False),
    # passes: more
    ("Bash", "command -v nmap", False),
    ("Bash", "command -pv nmap", False),
    ("Bash", "type nmap", False),
    ("Bash", "echo nmap", False),
    ("Bash", "ls nmap/ masscan.txt", False),
    ("Bash", "cat nmap.log > nmap.out", False),
    ("Bash", "cat < nmap.txt", False),
    ("Bash", 'echo "a; nmap"', False),
    ("Bash", "echo 'host", False),
    ("Bash", "nc -z -w 2 host.example 22", False),
    ("Bash", "nc -z host.example 22 -w 3", False),
    ("Bash", "nc host.example 22 80", False),
    ("Bash", "nc -l 8080", False),
    ("Bash", "ssh pi.example 'nc -z nas.example 22'", False),
    ("Bash", "ssh pi.example 'grep nmap /var/log/syslog'", False),
    ("Bash", "bash -c 'echo nmap'", False),
    ("Bash", "pip install python-nmap", False),
    ("Bash", "sync && once", False),
    ("Bash", "uptime", False),
    # case 1: a number directly before < or > belongs to the redirection, it is no port
    ("Bash", "nc -zv host.example 22 2>&1", False),
    ("Bash", "nc -zv host.example 22 2>&1 | grep -q succeeded", False),
    ("Bash", "nc -z host.example 22 >/dev/null", False),
    ("Bash", "nc -z host.example 22 &>/dev/null", False),
    ("Bash", "nc -zv host.example 22 80 2>&1", True),
    # case 2: ssh options after the host; options that take a value, also in a cluster
    ("Bash", "ssh pi.example -t 'sudo nmap -sS 192.0.2.0/24'", True),
    ("Bash", "ssh pi.example -p 2222 'nmap 192.0.2.0/24'", True),
    ("Bash", "ssh -vp 2222 pi.example 'nmap 192.0.2.0/24'", True),
    ("Bash", "ssh -P tag pi.example 'nmap 192.0.2.0/24'", True),
    ("Bash", "ssh -p2222 -l pi pi.example 'nmap 192.0.2.0/24'", True),
    ("Bash", "ssh pi.example -t uptime", False),
    ("Bash", "ssh -vp 2222 pi.example uptime", False),
    # case 3: text that runs nothing
    ("Bash", "git commit -m \"$(cat <<'EOF'\nhomenet: `nmap` is the owner's step\nEOF\n)\"", False),
    ("Bash", "cat > docs/scan.md <<'EOF'\n## Handoff\nnmap -sn 192.0.2.0/24\nEOF", False),
    ("Bash", "gh issue create --title x --body 'Run `nmap -sn` yourself'", False),
    ("Bash", "echo 'literal $(nmap x)'", False),
    ("Bash", "cat <<EOF\nnmap -sn 192.0.2.0/24\nEOF", False),
    ("Bash", "cat <<-EOF\n\tnmap -sn 192.0.2.0/24\n\tEOF", False),
    # case 3: a heredoc fed to a shell or to ssh is read
    ("Bash", "ssh pi.example <<'EOF'\nnmap 192.0.2.0/24\nEOF", True),
    ("Bash", "bash <<EOF\nnmap host.example\nEOF", True),
    ("Bash", "sudo bash <<'EOF'\nuptime\nnmap host.example\nEOF", True),
    ("Bash", "ssh -t pi.example <<'EOF'\nuptime; nc -z nas.example 20-25\nEOF", True),
    # case 3: an unquoted delimiter still expands, a command after the heredoc is still read
    ("Bash", "cat <<EOF\nhello $(nmap host.example)\nEOF", True),
    ("Bash", "cat <<EOF\nhello `nmap host.example`\nEOF", True),
    ("Bash", "cat <<EOF\nhello \\$(nmap host.example)\nEOF", False),
    ("Bash", "cat <<'EOF' > f.txt\ntext\nEOF\nnmap host.example", True),
    ("Bash", "cat <<'EOF'\nnmap x\nEOF\necho done", False),
    # case 4: watch runs its words through a shell
    ("Bash", "watch -n 5 'nmap -sn 192.0.2.0/24'", True),
    ("Bash", "watch \"nc -z host.example 20-25\"", True),
    ("Bash", "watch -dn 5 'echo x; nmap host.example'", True),
    ("Bash", "watch -n 5 uptime", False),
    ("Bash", "watch -n 5 'grep nmap notes.md'", False),
    # case 5: an unquoted backtick starts a command (Bash)
    ("Bash", "echo `sudo nmap host.example`", True),
    ("Bash", "x=`timeout 5 nmap host.example`", True),
    ("Bash", "echo \"a `sudo nmap host.example` b\"", True),
    ("Bash", "echo `date`", False),
    ("Bash", "echo \\`nmap host.example\\`", False),
    # case 6: nc options that take a value are no ports
    ("Bash", "nc -zw 2 host.example 22", False),
    ("Bash", "nc -z -G 2 host.example 22", False),
    ("Bash", "ncat -z --wait 2 host.example 22", False),
    ("Bash", "nc -zw 2 host.example 20-25", True),
    ("Bash", "nc -zw2 host.example 22", False),
    ("Bash", "ncat -z --wait=2 host.example 22 80", True),
    ("Bash", "ncat -z --wait 2 host.example 22 80", True),
    # more forms that start a command
    ("Bash", "if nmap host.example; then echo up; fi", True),
    ("Bash", "for h in a b; do nmap $h; done", True),
    ("Bash", "{ nmap host.example; }", True),
    ("Bash", "echo then nmap", False),
    ("Bash", "echo \"$(cd /tmp; (true); nmap host.example)\"", True),
    ("Bash", "diff <(nmap host.example) old.txt", True),
    ("Bash", "echo \"it's\" 'a \"quoted\" b' \"x $(date) y\"", False),
    # a comment (`#` at the start of a word, to the end of the line) is not read; the lines around it are
    ("Bash", "# Owner's network\nnmap -sn 192.0.2.0/24\n# Don't keep the output", True),
    ("Bash", "# Owner's network\nssh pi.example 'nmap -sn 192.0.2.0/24'\n# Don't keep it", True),
    ("Bash", "ssh pi.example uptime  # read only; nmap stays with the owner", False),
    ("Bash", "ssh pi.example uptime\n# step 2 (nmap) is the owner's\necho done", False),
    ("Bash", "ssh pi.example 'uptime  # then: nmap -sn 192.0.2.0/24'", False),
    ("Bash", "cat <<'EOF' # the owner's note\nnmap -sn 192.0.2.0/24\nEOF\necho done", False),
    # a `#` inside a word, inside quotes, in `$#` and in `${#x}` starts no comment
    ("Bash", "echo a#b; nmap host.example", True),
    ("Bash", "echo \"# text\"; nmap host.example", True),
    ("Bash", "echo '# text'; nmap host.example", True),
    ("Bash", "echo $#; nmap host.example", True),
    ("Bash", "echo ${#x}; nmap host.example", True),
    # nor does a `#` inside `$(( ))` or in a string for cmd, which knows no such comment
    ("Bash", "echo $(( 1 # 2 )); nmap host.example", True),
    ("Bash", "cmd /c \"dir # & nmap host.example\"", True),
    # a word split by a backslash and a newline is one word
    ("Bash", "nm\\\nap host.example", True),
    # options of a shell before `-c`, also with a value; the arguments of a script file are not read
    ("Bash", "bash -euo pipefail -c 'nmap host.example'", True),
    ("Bash", "bash -O extglob -c 'nmap host.example'", True),
    ("Bash", "bash -euo pipefail -c 'grep nmap notes.md'", False),
    ("Bash", "bash script.sh -c 'nmap host.example'", False),
    # options of a prefix word in a cluster
    ("Bash", "sudo -nu root nmap host.example", True),
    ("Bash", "sudo -nu root grep nmap notes.md", False),
    # the string handed to a PowerShell is read as PowerShell
    ("Bash", "powershell -Command 'Get-ChildItem | %{ nmap $_ }'", True),
    ("Bash", "pwsh -c 'Get-Content nmap.txt | %{ $_ }'", False),
]

POWERSHELL_CASES = [
    ("PowerShell", "nmap host.example", True),
    ("PowerShell", r"C:\Tools\nmap.exe host.example", True),
    ("PowerShell", r"& 'C:\Program Files\Nmap\nmap.exe' -sS 192.0.2.0/24", True),
    ("PowerShell", "NMAP.EXE host.example", True),
    ("PowerShell", "Write-Output x; nmap host.example", True),
    ("PowerShell", "Write-Output $(nmap host.example)", True),
    ("PowerShell", 'powershell -Command "nmap host.example"', True),
    ("PowerShell", "cmd /c nmap host.example", True),
    ("PowerShell", "ssh pi.example 'nmap 192.0.2.0/24'", True),
    ("PowerShell", "nc -z host.example 20-80", True),
    ("PowerShell", "Get-Content nmap.txt", False),
    ("PowerShell", r"Get-Content C:\logs\nmap.log", False),
    ("PowerShell", "Select-String -Pattern nmap -Path notes.md", False),
    ("PowerShell", "Test-NetConnection host.example -Port 22", False),
    ("PowerShell", "Write-Output 'nmap'", False),
    # case 5: in PowerShell the backtick is the escape character
    ("PowerShell", "Write-Output \"a`tb\"", False),
    ("PowerShell", "Write-Output \"`nmap\"", False),
    ("PowerShell", "Write-Output `nmap", False),
    ("PowerShell", "Write-Output \"`\"; nmap host.example\"", False),
    ("PowerShell", "nc -zv host.example 22 2>&1", False),
    ("PowerShell", "ssh pi.example -t 'nmap 192.0.2.0/24'", True),
    ("PowerShell", "Start-Job { nmap host.example }", True),
    ("PowerShell", "{ nmap host.example }", True),
    ("PowerShell", "Invoke-Command -ComputerName pi.example -ScriptBlock { nmap 192.0.2.0/24 }", True),
    ("PowerShell", "Get-ChildItem | ForEach-Object { nmap $_ }", True),
    ("PowerShell", "& { nmap host.example }", True),
    ("PowerShell", "Get-ChildItem | Where-Object { $_.Name -like 'nmap*' }", False),
    ("PowerShell", "$h = @{ nmap = 1 }", False),
    ("PowerShell", "Write-Output \"${nmap}\"", False),
    ("PowerShell", "Write-Output ${nmap}", False),
    # comments: `#` at the start of a word to the end of the line, and `<# ... #>`
    ("PowerShell", "# Owner's network\nnmap -sn 192.0.2.0/24\n# Don't keep the output", True),
    ("PowerShell", "Test-NetConnection nas.example -Port 22  # no scan; nmap is for the owner", False),
    ("PowerShell", "<# nmap is the owner's step #>\nWrite-Output x", False),
    ("PowerShell", "<# the owner's step #> nmap host.example", True),
    ("PowerShell", "Write-Output a#b; nmap host.example", True),
    # a script block starts a command after any word but `@` and `$`
    ("PowerShell", "1..3 | %{ nmap \"192.0.2.$_\" }", True),
    ("PowerShell", "Get-ChildItem | ?{ nmap $_ }", True),
    ("PowerShell", "ForEach-Object{ nmap $_ }", True),
    # a here-string is one word: `@'` is text, `@"` still runs `$( )`; what follows it is read
    ("PowerShell", "git commit -m @'\nhomenet: don't let the assistant scan\n\nnmap and masscan are refused.\n'@", False),
    ("PowerShell", "git commit -m @'\r\nhomenet: don't scan; nmap is refused.\r\n'@", False),
    ("PowerShell", "Set-Content -Path docs/handoff.md -Value @'\n# Handoff\nnmap -sn 192.0.2.0/24\nThe owner's step.\n'@",
     False),
    ("PowerShell", "Set-Content -Path docs/handoff.md -Value @\"\n# Handoff\nnmap -sn 192.0.2.0/24\nThe owner's step.\n\"@",
     False),
    ("PowerShell", "Write-Output @\"\nopen: $(nmap host.example)\n\"@", True),
    ("PowerShell", "Write-Output @'\nopen: $(nmap host.example)\n'@", False),
    ("PowerShell", "Set-Content -Path a.md -Value @'\nThe owner's step.\n'@\nnmap host.example", True),
    ("PowerShell", "ssh pi.example @'\nuptime\nnmap -sn 192.0.2.0/24\n'@", True),
    # Invoke-Expression reads its string like eval
    ("PowerShell", "Invoke-Expression 'nmap -sn 192.0.2.0/24'", True),
    ("PowerShell", "iex 'nmap -sn 192.0.2.0/24'", True),
    ("PowerShell", "Invoke-Expression -Command 'nmap -sn 192.0.2.0/24'", True),
    ("PowerShell", "Invoke-Expression 'Get-Content nmap.txt'", False),
    # a stream before `>` belongs to the redirection, it is no port
    ("PowerShell", "nc -zv host.example 22 *>$null", False),
    ("PowerShell", "nc -zv host.example 22 *>&1", False),
    ("PowerShell", "nc -zv host.example 22 2>$null", False),
    ("PowerShell", "nc -zv host.example 22 80 *>$null", True),
    # a word split by a backtick is one word
    ("PowerShell", "n`map host.example", True),
    # the closing brace of a script block ends its command, it is no port
    ("PowerShell", "Invoke-Command -ComputerName pi.example -ScriptBlock { nc -z nas.example 22 }", False),
    ("PowerShell", "if ($up) { nc -z nas.example 22 } else { Write-Output down }", False),
    ("PowerShell", "Invoke-Command -ComputerName pi.example -ScriptBlock { nc -z nas.example 20-25 }", True),
    # the remote command of ssh is read as a POSIX shell reads it
    ("PowerShell", "ssh pi.example \"cat > notes.md <<'EOF'\nnmap -sn 192.0.2.0/24\nEOF\"", False),
    # `${name}` stays one word, and a backslash written in PowerShell stays a path separator in a remote command
    ("PowerShell", "nc -zv ${target} 20-25", True),
    ("PowerShell", "nc -zv ${target} 22", False),
    ("PowerShell", r"ssh win.example C:\Tools\nmap.exe -sn 192.0.2.0/24", True),
    ("PowerShell", r"ssh win.example type C:\logs\nmap.log", False),
]

OTHER_TOOL_CASES = [
    {"tool_name": "Read", "tool_input": {"file_path": "/home/user/notes/nmap-usage.md"}},
    {"tool_name": "Grep", "tool_input": {"pattern": "nmap", "path": "docs"}},
    {"tool_name": "Write", "tool_input": {"file_path": "scan-nmap.txt", "content": "nmap host.example"}},
    {"tool_name": "Edit", "tool_input": {"file_path": "a.md", "old_string": "nmap x", "new_string": "masscan y"}},
    {"tool_name": "mcp__demo__run", "tool_input": {"command": "nmap host.example"}},
    {"tool_name": "Bash"},
    {"tool_name": "Bash", "tool_input": {}},
    {"tool_name": "Bash", "tool_input": {"command": ""}},
    {"tool_name": "Bash", "tool_input": {"command": None}},
    {"tool_name": "Bash", "tool_input": "nmap host.example"},
    {"tool_name": "Bash", "tool_input": {"description": "nmap host.example"}},
    {"tool_input": {"command": "nmap host.example"}},
    {},
]


def call(payload: Dict[str, Any]) -> "tuple[int, str]":
    """The verdict of the check and what it wrote to stderr."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        verdict = MODULE.check_homenet_no_scan(payload)
    return verdict, err.getvalue()


def payload_of(tool: str, command: Optional[str]) -> Dict[str, Any]:
    return {"tool_name": tool, "tool_input": {"command": command}, "cwd": "/tmp", "session_id": "s1"}


class CheckHomenetNoScanTest(unittest.TestCase):
    def assert_verdict(self, tool: str, command: str, refused: bool) -> None:
        verdict, stderr = call(payload_of(tool, command))
        if refused:
            self.assertEqual(verdict, 2, f"{tool} command {command!r} should be refused")
            self.assertIn("R-homenet-never", stderr, f"reason for {command!r} must name the rule")
            self.assertIn("owner", stderr)
        else:
            self.assertEqual(verdict, 0, f"{tool} command {command!r} should pass (stderr: {stderr!r})")
            self.assertEqual(stderr, "", f"a pass must print nothing for {command!r}")

    def test_bash_cases(self) -> None:
        for tool, command, refused in BASH_CASES:
            with self.subTest(command=command):
                self.assert_verdict(tool, command, refused)

    def test_powershell_cases(self) -> None:
        for tool, command, refused in POWERSHELL_CASES:
            with self.subTest(command=command):
                self.assert_verdict(tool, command, refused)

    def test_other_tools_and_missing_fields_pass(self) -> None:
        for payload in OTHER_TOOL_CASES:
            with self.subTest(payload=payload):
                verdict, stderr = call(payload)
                self.assertEqual((verdict, stderr), (0, ""))

    def test_payload_is_not_a_dict_passes(self) -> None:
        self.assertEqual(call([])[0], 0)  # type: ignore[arg-type]

    def test_reason_names_the_word_not_the_command(self) -> None:
        verdict, stderr = call(payload_of("Bash", "nmap -sS secret-host.example"))
        self.assertEqual(verdict, 2)
        self.assertIn("`nmap`", stderr)
        self.assertNotIn("secret-host.example", stderr)

    def test_payload_is_not_changed(self) -> None:
        payload = payload_of("Bash", "echo x && nmap host.example")
        before = repr(payload)
        call(payload)
        self.assertEqual(repr(payload), before)

    def test_nesting_deeper_than_the_limit_is_refused(self) -> None:
        command = "nmap host.example"
        for _ in range(8):
            command = "bash -c " + shlex.quote(command)
        verdict, stderr = call(payload_of("Bash", command))
        self.assertEqual(verdict, 2)
        self.assertIn("R-homenet-never", stderr)

    def test_nesting_within_the_limit_is_read(self) -> None:
        command = "nmap host.example"
        for _ in range(3):
            command = "bash -c " + shlex.quote(command)
        self.assertEqual(call(payload_of("Bash", command))[0], 2)
        harmless = "echo nmap"
        for _ in range(3):
            harmless = "bash -c " + shlex.quote(harmless)
        self.assertEqual(call(payload_of("Bash", harmless))[0], 0)

    def test_long_command_lines_are_judged(self) -> None:
        filler = "echo " + "word " * 4000
        self.assertEqual(call(payload_of("Bash", filler))[0], 0)
        self.assertEqual(call(payload_of("Bash", filler + "; nmap host.example"))[0], 2)

    def test_large_heredoc_in_a_commit_is_judged_fast(self) -> None:
        body = "homenet: `nmap` is the owner's step; run nmap -sn 192.0.2.0/24 yourself\n" * 2800  # about 200 KB
        command = "git commit -m \"$(cat <<'EOF'\n" + body + "EOF\n)\""
        started = time.perf_counter()
        verdict, _ = call(payload_of("Bash", command))
        elapsed = time.perf_counter() - started
        self.assertEqual(verdict, 0)
        self.assertLess(elapsed, 2.0, f"a 200 KB heredoc took {elapsed:.2f} s")
        verdict, _ = call(payload_of("Bash", command + "\nnmap host.example"))
        self.assertEqual(verdict, 2)

    def test_large_here_string_is_judged_fast(self) -> None:
        body = "homenet: `nmap` is the owner's step; run nmap -sn 192.0.2.0/24 yourself\n" * 2800  # about 200 KB
        command = "Set-Content -Path docs/handoff.md -Value @'\n" + body + "'@"
        started = time.perf_counter()
        verdict, _ = call(payload_of("PowerShell", command))
        elapsed = time.perf_counter() - started
        self.assertEqual(verdict, 0)
        self.assertLess(elapsed, 2.0, f"a 200 KB here-string took {elapsed:.2f} s")
        verdict, _ = call(payload_of("PowerShell", command + "\nnmap host.example"))
        self.assertEqual(verdict, 2)

    def test_long_line_with_a_scanner_word_is_judged_fast(self) -> None:
        command = "echo " + "word " * 1000 + "nmap-notes.md; echo x"
        started = time.perf_counter()
        verdict, _ = call(payload_of("Bash", command))
        elapsed = time.perf_counter() - started
        self.assertEqual(verdict, 0)
        self.assertLess(elapsed, 2.0, f"a long line took {elapsed:.2f} s")

    def test_module_has_no_relative_import(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^\s*from\s+\.")


if __name__ == "__main__":
    unittest.main()
