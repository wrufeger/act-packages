"""homenet_no_scan: refuse port scanners in shell calls (rule R-homenet-never).

A PreToolUse check of the package `homenet`. It judges the command of a `Bash` or `PowerShell` call and refuses when
a command word is a port scanner. Other tools pass. It reads the command text only and never runs anything. It is one
barrier of two: the rule holds without it (a script that opens connections itself is still a scan).

How it reads: one pass over the text with a small lexer for the two shells (quotes, escapes, comments, redirections,
`$( )`, backticks and heredocs; in PowerShell also script blocks, here-strings and `<# #>`). Every command that ends
is judged: the command word after assignments and prefix words (`sudo`, `env`, `timeout`, ...), and the text a command
hands to a shell (`ssh`, `bash -c`, `watch`, `eval`, `Invoke-Expression`, `powershell -Command`, `cmd /c`, a heredoc
fed to a shell or to ssh) is read the same way, as the shell that gets it reads it, up to a nesting depth. Text that
runs nothing is not read: comments, single quotes, a `@'` here-string, a heredoc with a quoted delimiter that goes to
a program other than a shell or ssh. A heredoc with an unquoted delimiter and a `@"` here-string still expand, so the
`$( )` in their bodies are read (in a heredoc backticks too). Quoting the lexer cannot close falls back to splitting
on whitespace.

Known limits. Not caught: `env -S '...'`, `su -c '...'`, `cmd //c`, a here-string fed to a shell (`bash <<< 'nmap
x'`), a heredoc for `sudo -s` or piped on (`cat <<EOF | bash`, `| ssh`), a string piped to `Invoke-Expression`, `find
-exec nmap`, `Start-Process nmap`, PowerShell `$r = nmap ...` and other assignments that hold a command, variables and
aliases that stand for a scanner, `$'...'` strings with escaped quotes, a script or program that opens connections
itself, a loop of single probes (`ping`, `Test-Connection`, `nc -z` per address or port), and a program fed a heredoc
that is not a shell or ssh (`python <<EOF`). Misread, so that a harmless call may
be refused or a scan missed: `tools=(nmap masscan)`, `case ... in nmap|masscan)`, `$(case ...)`, `<<$'EOF'`, a
multi-line `@{ ... }` hashtable, a PowerShell backtick before CRLF as line continuation, and ssh with a remote
command plus a heredoc body.

The dispatcher loads this file from its bytes, so it imports only the standard library.
"""
from __future__ import annotations

import re
import sys
from typing import List, NamedTuple

_SHELL_TOOLS = ("Bash", "PowerShell")
_SCANNERS = frozenset({"nmap", "masscan", "zmap", "rustscan", "naabu", "unicornscan"})
_NETCATS = frozenset({"nc", "ncat", "netcat", "nc.openbsd", "nc.traditional"})
_MAX_DEPTH = 4  # nested ssh / bash -c / $( ) / heredoc levels that are read; deeper cannot be judged and is refused

_NO_WORDS: frozenset = frozenset()
# Prefix word -> (letters of its options that take a value, its long options that take one, plain words between the
# options and the command). A cluster whose last letter takes a value takes the next word (`sudo -nu root`); `-n5`
# carries its own.
_PREFIX = {
    "sudo": ("CDRTUghprtu", frozenset({"--user", "--group", "--host"}), 0),
    "doas": ("Cu", _NO_WORDS, 0),
    "env": ("Cu", frozenset({"--unset", "--chdir"}), 0),
    "timeout": ("ks", frozenset({"--signal", "--kill-after"}), 1),
    "nice": ("n", frozenset({"--adjustment"}), 0),
    "nohup": ("", _NO_WORDS, 0),
    "time": ("fo", _NO_WORDS, 0),
    "command": ("", _NO_WORDS, 0),
    "exec": ("a", _NO_WORDS, 0),
    "xargs": ("adEILlnPs", _NO_WORDS, 0),
}
# Commands that run their words through a shell: the same three values (here options may also follow the plain
# words), and whether that shell is PowerShell.
_RUNNERS = {
    "ssh": ("BbcDEeFIiJLlmOoPpQRSWw", _NO_WORDS, 1, False),  # ssh(1); the plain word is the host, its shell POSIX
    "watch": ("n", frozenset({"--interval"}), 0, False),
    "eval": ("", _NO_WORDS, 0, False),
    "iex": ("", _NO_WORDS, 0, True),
    "invoke-expression": ("", _NO_WORDS, 0, True),
}
_POSIX_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "ash"})
_COMMAND_FLAGS = {"pwsh": ("-c", "-command"), "powershell": ("-c", "-command"), "cmd": ("/c", "/k")}
# Words that only introduce a command: the command word is the next one.
_LEADING = frozenset({"if", "then", "elif", "else", "do", "while", "until", "!", "{"})

# nc / ncat manuals (OpenBSD, BSD, traditional, Nmap's ncat). Letters that mean a value in one flavour and a flag in
# another (`c`, `C`, `d`, `H`, `K`, `R`) are left out: a missed value only makes the check refuse more.
_NC_VALUE_LETTERS = "eGgIiMmOoPpqsTVWwXx"
_NC_LONG_VALUES = frozenset({
    "--wait", "--idle-timeout", "--delay", "--source", "--source-port", "--exec", "--sh-exec", "--lua-exec",
    "--proxy", "--proxy-type", "--proxy-auth", "--allow", "--allowfile", "--deny", "--denyfile", "--max-conns",
    "--output", "--hex-dump", "--ssl-cert", "--ssl-key", "--ssl-trustfile", "--ssl-ciphers", "--ssl-servername",
    "--ssl-alpn", "--connect-timeout", "--nsock-engine", "--lua-exec-internal",
})

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_LOOKUP_FLAGS = re.compile(r"^-[A-Za-z]*[vV][A-Za-z]*$")
_SHORT_CLUSTER = re.compile(r"^-[A-Za-z]+$")
# Quick look before any parsing: a command without one of these words cannot be refused, and a long unrelated command
# line costs two regex searches: the text as it is, and with what can split a word taken out, so `n"m"ap` is caught.
_HINT = re.compile(r"nmap|masscan|zmap|rustscan|naabu|unicornscan|ncat|netcat|\bnc\b", re.IGNORECASE)
_SH_SPLITTERS = re.compile(r"\\\n|[\"'\\]")
_PS_SPLITTERS = re.compile(r"[\"'`]")

_SH_PLAIN = re.compile(r"[^ \t\r\n;&|()<>'\"\\$`]+")
_PS_PLAIN = re.compile(r"[^ \t\r\n;&|()<>'\"$`{}]+")  # a backslash is plain in PowerShell, a brace is not
_SH_EXPANDING = re.compile(r"[\"\\$`]")
_PS_EXPANDING = re.compile(r"[\"$`]")
_REDIRECTION = re.compile(r"<<<|<[&>]?|>[>&|]?")
_HEREDOC = re.compile(r"<<(-?)[ \t]*((?:[^ \t\r\n;&|()<>'\"\\]+|'[^']*'|\"[^\"]*\"|\\.)+)")
_HEREDOC_QUOTING = re.compile(r"['\"\\]")
_HERE_STRING = re.compile(r"@['\"][ \t]*\r?\n")
_BACKTICKED = re.compile(r"((?:[^`\\]+|\\[\s\S])*)\\?`?")
_BACKTICK_ESCAPE = re.compile(r"\\([`\\$])")


class _Refused(Exception):
    """A command that must not run; the text is the reason."""


class _Unparsable(Exception):
    """Quoting that does not close."""


class _Heredoc(NamedTuple):
    delimiter: str
    quoted: bool  # the delimiter was quoted: the body is not expanded
    strip_tabs: bool  # `<<-`
    words: List[str]  # the command the heredoc is fed to


def _base_name(word: str) -> str:
    """The command name of a word: no folder, lower case, no `.exe`."""
    name = re.split(r"[\\/]", word)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _index(text: str, mark: str, start: int) -> int:
    """Where `mark` begins at or after `start`; the end of the text when it does not come."""
    found = text.find(mark, start)
    return len(text) if found < 0 else found


def _option_width(word: str, value_letters: str, long_values: frozenset) -> int:
    """How many words an option word takes: 2 when its value is the next word, else 1.

    `-p2222` carries its value, `-vp` (last letter takes a value) does not, `--wait=2` carries it, `--wait` does not.
    """
    if word.startswith("--"):
        return 2 if word in long_values else 1
    for position, letter in enumerate(word[1:], start=1):
        if letter in value_letters:
            return 1 if position < len(word) - 1 else 2
    return 1


def _after_options(words: List[str], position: int, value_letters: str, long_values: frozenset, plain: int) -> int:
    """Index of the word after the options from `position` on, their values and `plain` plain words among them.

    For `ssh -p 2222 host -t command` (one plain word, the host) that is `command`; `--` ends the options.
    """
    while position < len(words):
        word = words[position]
        if word == "--":
            return position + 1 + plain
        if word.startswith("-") and word != "-":
            position += _option_width(word, value_letters, long_values)
        elif plain:
            plain -= 1
            position += 1
        else:
            break
    return position


def _command_index(words: List[str]) -> int:
    """Index of the command word of one command, after assignments, leading words and prefix words; -1 if none."""
    index = 0
    while index < len(words):
        word = words[index]
        name = _base_name(word)
        if _ASSIGNMENT.match(word) or word in _LEADING:
            index += 1
        elif name not in _PREFIX:
            return index
        else:
            value_letters, long_values, plain = _PREFIX[name]
            first, index = index + 1, _after_options(words, index + 1, value_letters, long_values, 0)
            if name == "command" and any(_LOOKUP_FLAGS.match(option) for option in words[first:index]):
                return -1  # `command -v name` only looks the name up
            index += plain
    return -1


def _shell_string(words: List[str], index: int, name: str) -> str:
    """The command string a shell is given (`bash -c '...'`, `powershell -Command ...`, `cmd /c ...`), or ""."""
    position = index + 1
    if name in _COMMAND_FLAGS:  # every word after the flag
        while position < len(words) and words[position].lower() not in _COMMAND_FLAGS[name]:
            position += 1
        return " ".join(words[position + 1:])
    while position < len(words) and words[position][:1] in ("-", "+"):  # a POSIX shell: the word after `-c`
        word = words[position]
        if _SHORT_CLUSTER.match(word) and "c" in word:
            return " ".join(words[position + 1:position + 2])
        position += _option_width(word, "oO", _NO_WORDS)
    return ""


def _is_port_sweep(words: List[str], index: int) -> bool:
    """`nc -z` (alone or in a cluster such as `-zv`) over a port range or more than one port."""
    zero_io = False
    positionals: List[str] = []
    options_done = False
    position = index + 1
    while position < len(words):
        word = words[position]
        if not options_done and word == "--":
            options_done = True
            position += 1
        elif not options_done and len(word) > 1 and word.startswith("-"):
            if not word.startswith("--"):
                for letter in word[1:]:
                    zero_io = zero_io or letter == "z"
                    if letter in _NC_VALUE_LETTERS:
                        break
            position += _option_width(word, _NC_VALUE_LETTERS, _NC_LONG_VALUES)
        else:
            positionals.append(word)
            position += 1
    ports = positionals[1:]  # the first positional word is the host
    return zero_io and (len(ports) > 1 or any("-" in port or "," in port for port in ports))


def _judge_words(words: List[str], depth: int, powershell: bool) -> None:
    """Raise _Refused when one command (its words) is a scan, or hands a scan to a shell."""
    index = _command_index(words)
    if index < 0:
        return
    name = _base_name(words[index])
    if name in _SCANNERS:
        raise _Refused(f"`{name}` is a port scanner")
    if name in _NETCATS and _is_port_sweep(words, index):
        raise _Refused(f"`{name} -z` over several ports is a port scan")
    nested, from_powershell = "", powershell
    if name in _RUNNERS:
        value_letters, long_values, plain, powershell = _RUNNERS[name]
        nested = " ".join(words[_after_options(words, index + 1, value_letters, long_values, plain):])
    elif name in _POSIX_SHELLS or name in _COMMAND_FLAGS:
        nested = _shell_string(words, index, name)
        if name == "cmd":  # read as the shell around it, but cmd knows no `#` comment
            nested = nested.replace("#", "_")
        else:
            powershell = name in _COMMAND_FLAGS
    if from_powershell and not powershell:  # written in PowerShell, a backslash is a path separator, no escape
        nested = nested.replace("\\", "/")
    if nested:
        _scan(nested, depth + 1, powershell)


class _Lexer:
    """Reads a command line once, left to right, and judges every command as it ends (raises _Refused).

    Words lose their quotes; a substitution (`$( )`, backticks) leaves a NUL in the word and its text is read as a
    command line of its own. A number directly before `<` or `>` and the target of a redirection are no words.
    """

    def __init__(self, text: str, depth: int, powershell: bool, pos: int = 0) -> None:
        self.text = text
        self.depth = depth
        self.powershell = powershell
        self.pos = pos
        self.words: List[str] = []
        self.piece: List[str] = []
        self.in_word = False
        self.skip_target = False
        self.pending: List[_Heredoc] = []

    def add(self, text: str) -> None:
        """Text for the word being read."""
        self.piece.append(text)
        self.in_word = True

    def end_word(self) -> None:
        if self.in_word:
            if not self.skip_target:
                self.words.append("".join(self.piece))
            self.skip_target = False
            self.piece.clear()
            self.in_word = False

    def end_command(self) -> None:
        self.end_word()
        self.skip_target = False
        words, self.words = self.words, []  # a new list: a heredoc keeps the words of its command
        if words:
            _judge_words(words, self.depth, self.powershell)

    def lex(self, nested: bool) -> int:
        """Read to the end, or to the `)` that closes a `$(` when `nested`; returns the position after it."""
        if self.depth > _MAX_DEPTH:
            raise _Refused(f"it nests commands deeper than {_MAX_DEPTH} levels and cannot be judged")
        text, size, powershell = self.text, len(self.text), self.powershell
        plain = _PS_PLAIN if powershell else _SH_PLAIN
        parens = 0
        braces: List[bool] = []  # the open braces of PowerShell: True for `@{` and `${`, False for a script block
        comments = not (nested and text.startswith("(", self.pos))  # `$(( ))` is arithmetic: a `#` is no comment
        while self.pos < size:
            pos = self.pos
            char = text[pos]
            if char in " \t\r":
                self.end_word()
                self.pos += 1
            elif char == "\n":
                self.end_command()
                self.pos += 1
                if self.pending:
                    self.read_bodies()
            elif char == "#" and comments and not self.in_word:  # a comment: to the end of the line
                self.pos = _index(text, "\n", pos)
            elif char == "<" and powershell and text.startswith("#", pos + 1):  # a block comment: to its `#>`
                self.end_word()
                self.pos = _index(text, "#>", pos + 2) + 2
            elif char == "@" and powershell and not self.in_word and _HERE_STRING.match(text, pos):
                self.here_string()
            elif char in ";|(":
                self.end_command()
                self.pos += 1
                if char == "(":
                    parens += 1
            elif char == ")":
                self.end_command()
                self.pos += 1
                if parens:
                    parens -= 1
                elif nested:
                    return self.pos
            elif char == "&":
                if text.startswith("&>", pos):  # `&>file` and `&>>file`
                    self.end_word()
                    self.pos += 3 if text.startswith("&>>", pos) else 2
                    self.skip_target = True
                else:
                    self.end_command()
                    self.pos += 1
            elif char in "<>":
                self.redirection()
            elif char == "'":
                end = text.find("'", pos + 1)
                if end < 0:
                    raise _Unparsable()
                self.add(text[pos + 1:end])
                self.pos = end + 1
            elif char == '"':
                self.expanding(pos + 1, True)
            elif char == "$":
                if text.startswith("(", pos + 1):
                    self.pos = self.substitute(pos + 2)
                else:
                    self.add("$")
                    self.pos += 1
            elif char == "`" and not powershell:
                self.pos = self.backtick(pos + 1)
            elif char == ("`" if powershell else "\\"):  # the escape character: the next one is plain
                following = text[pos + 1:pos + 2]
                self.pos += 2
                if following == "\n":  # a continuation line: Bash joins the word, PowerShell ends it
                    if powershell:
                        self.end_word()
                elif following:
                    self.add(following)
            elif char in "{}" and powershell:
                if char == "{":
                    braces.append(pos > 0 and text[pos - 1] in "@$")
                    data = braces[-1]
                else:
                    data = bool(braces) and braces.pop()
                if data:  # `@{ }` and `${ }` hold data: the brace stays in its word
                    self.add(char)
                else:  # a script block starts a command, and its end ends one
                    self.end_command()
                self.pos += 1
            else:
                run = plain.match(text, pos)
                self.add(run.group() if run else char)
                self.pos = run.end() if run else pos + 1
        self.end_command()
        return size

    def redirection(self) -> None:
        """`<`, `>` and their forms: a number directly before (in PowerShell also `*`) is part of it and the target
        word is dropped; a heredoc is remembered for the next newline, a process substitution is read."""
        text, pos = self.text, self.pos
        before = "".join(self.piece)
        if self.in_word and (before.isdigit() or (self.powershell and before == "*")):
            self.piece.clear()
            self.in_word = False
        self.end_word()
        heredoc = None if self.powershell or text.startswith("<<<", pos) else _HEREDOC.match(text, pos)
        if text.startswith("(", pos + 1):  # `<( )`, `>( )`: a command inside, a file name for the word
            self.pos = self.substitute(pos + 2)
        elif heredoc:
            raw = heredoc.group(2)
            delimiter = _HEREDOC_QUOTING.sub("", raw)
            self.pending.append(_Heredoc(delimiter, delimiter != raw, bool(heredoc.group(1)), self.words))
            self.pos = heredoc.end()
        else:
            operator = _REDIRECTION.match(text, pos)
            self.pos = operator.end() if operator else pos + 1
            self.skip_target = True

    def read_bodies(self) -> None:
        """Read the bodies of the pending heredocs, from the line after the newline just passed: a script when fed
        to a shell or to ssh, for any other command text that still expands unless the delimiter was quoted."""
        text = self.text
        for heredoc in self.pending:
            tabs = r"\t*" if heredoc.strip_tabs else ""
            end_line = re.compile(rf"(?m)^{tabs}{re.escape(heredoc.delimiter)}\r?$").search(text, self.pos)
            start = self.pos
            stop, self.pos = end_line.span() if end_line else (len(text), len(text))
            index = _command_index(heredoc.words)
            name = _base_name(heredoc.words[index]) if index >= 0 else ""
            if name in _POSIX_SHELLS or name == "ssh":
                _scan(text[start:stop], self.depth + 1, False)
            elif not heredoc.quoted:
                _Lexer(text[start:stop], self.depth, False).expanding(0, False)
        self.pending = []

    def here_string(self) -> None:
        """A PowerShell here-string at the position (`@'` or `@"`, a newline, lines, then `'@` or `"@` at the start
        of a line): one word. Only the `@"` form expands, so the `$( )` in its body are read."""
        text = self.text
        quote = text[self.pos + 1]
        start = text.index("\n", self.pos) + 1
        close = text.find(f"\n{quote}@", start - 1)
        if close < 0:
            raise _Unparsable()
        if quote == '"':
            _Lexer(text[start:close], self.depth, True).expanding(0, False)
        self.add(text[start:close])
        self.pos = close + 3

    def expanding(self, pos: int, quoted: bool) -> None:
        """Text that only expands, from `pos`: a double-quoted string up to its closing quote when `quoted`, else a
        whole heredoc or here-string body. The substitutions in it are read, the rest is text of the word."""
        text = self.text
        special = _PS_EXPANDING if self.powershell else _SH_EXPANDING
        while True:
            found = special.search(text, pos)
            if found is None and quoted:
                raise _Unparsable()
            if found is None or (quoted and found.group() == '"'):
                break
            self.add(text[pos:found.start()])
            char, pos = found.group(), found.end()
            following = text[pos:pos + 1]
            if char == "$" and following == "(":
                pos = self.substitute(pos + 1)
            elif char in '$"':
                self.add(char)
            elif self.powershell:  # a backtick: the next character is plain
                self.add(following)
                pos += 1
            elif char == "`":
                pos = self.backtick(pos)
            elif following and following in "$`\"\\":  # a backslash before one of these: that character, plain
                self.add(following)
                pos += 1
            elif following != "\n":
                self.add(char)
            else:  # a continuation line
                pos += 1
        if found:
            self.add(text[pos:found.start()])
            pos = found.end()
        self.pos = pos

    def substitute(self, pos: int) -> int:
        """`$(` ... `)` or `<(` ... `)` from `pos`, just after the opening: read inside, return the position after."""
        self.add("\0")
        return _Lexer(self.text, self.depth + 1, self.powershell, pos).lex(True)

    def backtick(self, pos: int) -> int:
        """A backtick substitution from `pos`, just after the opening backtick: read inside (`\\``, `\\\\` and `\\$`
        lose their backslash first), return the position after the closing backtick."""
        found = _BACKTICKED.match(self.text, pos)
        assert found is not None  # every part of the pattern may match the empty string
        self.add("\0")
        _scan(_BACKTICK_ESCAPE.sub(r"\1", found.group(1)), self.depth + 1, False)
        return found.end()


def _scan_split(text: str, depth: int, powershell: bool) -> None:
    """The fallback for quoting that does not close: split on whitespace and operators, strip quote characters."""
    spaced = text.replace("$(", " ( ").replace("\n", " ; ")
    spaced = re.sub(r"[;&|()<>]" if powershell else r"[;&|()<>`]", lambda m: f" {m.group(0)} ", spaced)
    words: List[str] = []
    drop_next = False
    for raw in spaced.split():
        token = raw.strip("'\"")
        if not token:
            continue
        if len(token) == 1 and token in ";&|()<>`":
            if token in "<>":
                drop_next = True
                continue
            drop_next = False
            _judge_words(words, depth, powershell)
            words = []
        elif drop_next:
            drop_next = False
        else:
            words.append(token)
    _judge_words(words, depth, powershell)


def _scan(text: str, depth: int, powershell: bool) -> None:
    """Raise _Refused when a command line (a call's command, a remote command, a `-c` string) holds a scan."""
    try:
        _Lexer(text, depth, powershell).lex(False)
    except _Unparsable:
        _scan_split(text, depth, powershell)


def check_homenet_no_scan(payload: dict) -> int:
    """0 lets the call pass, 2 refuses it (the reason goes to stderr)."""
    if not isinstance(payload, dict) or payload.get("tool_name") not in _SHELL_TOOLS:
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0
    powershell = payload.get("tool_name") == "PowerShell"
    joined = (_PS_SPLITTERS if powershell else _SH_SPLITTERS).sub("", command)
    if not _HINT.search(command) and not _HINT.search(joined):
        return 0
    try:
        _scan(command, 0, powershell)
    except _Refused as refusal:
        print(
            f"[homenet] refused: {refusal}. R-homenet-never: the assistant never runs a port scan or any tool that "
            f"sweeps ports; a scan is the owner's step. Hand it over as a todo with the exact command and the reason "
            f"(R-homenet-handoff).",
            file=sys.stderr,
        )
        return 2
    return 0
