# Creating a package

A package is a folder under `packages/<id>/`. The template reads it with `python .act/scripts/packages.py plan <folder>`,
which checks it and prints what installing it would do; it writes nothing and runs no package code. Start from
`packages/example/`.

## Layout

```
<id>/
  package.md        required
  install.py        optional, code that runs once at install (needs contains-code: yes)
  install.md        optional, the AI-guided setup, read after the install
  pre-template/     units that come before the template's own
  post-template/    units that come after the template's own
```

Each side holds any of `rules/`, `coding/`, `skills/`, `agents/`, `topics/`, `scripts/`, `hooks/checks/`, nothing else.
No symbolic links, no `:` in a name, no Windows device names (`con`, `nul`, `com1` ...).

## package.md

A header between two `---` lines (`id`, `version` as `X.Y.Z`, `requires-template` as `>=X.Y.Z`, `tools`, `license`,
`contains-code` as `yes` or `no`; optionally `stack`, a comma list of the stacks the package is for, which the catalogue
index carries and nothing checks), then sections: `## Contents` (free text), and optionally `## disables`
(`- R-<area>-<name>`), `## settings` (`- <id>-<key>: <question>`) and `## checks` (`- <check>: block|warn|off`).
Any other section is refused. The id starts with a letter and holds lowercase letters, digits and hyphens, 2 to 31
characters (`^[a-z][a-z0-9-]{1,30}$`); `act` and `act-...` are the template's.

## Names

- A new unit is named `<id>-<name>`: skill folder, role file, topic, coding set; rule ids `R-<id>-<name>`; scripts and
  check modules `<id>_<name>.py` (hyphens of the id become underscores).
- A unit with a template unit's name **replaces** it from `pre-template/` and **extends** it (text appended) from
  `post-template/`. Coding sets and rules are only extended.
- To replace a template rule: list its id under `## disables` and bring an own rule `R-<id>-<name>` in `pre-template/`.
  A template rule id in `pre-template/` is always refused. A template rule id in `post-template/` extends that rule.
- A script or check module never takes a template one's name. Another package's unit name is refused.

## Code

`install.py` runs once, after the owner said yes to the plan, in the project root, with no input and a 300 second limit.
A check module in `hooks/checks/` defines `check_<module>(payload) -> int` (0 passes, 2 refuses, stderr is the reason)
and can only make a call stricter. Both need `contains-code: yes` and are trusted code once installed; keep them short
and say in `## Contents` what they do. `install.md` is the instruction for the assistant after the install.

## Test it

From the root of a project on the template (the plan needs its `.act/`):

```
python .act/scripts/packages.py plan <path to act-packages>/packages/<id>
```

From the root of this repository (runs that plan for every package in a throwaway copy of the template):

```
python tools/build.py --template <path to a template checkout>
```

The plan prints every reason a package is refused, not only the first.

## Submit and sign

Open a pull request with `packages/<id>/`. Raise `version` for every change that should reach projects. The maintainers
build, sign and publish the zip; authors do not sign.
