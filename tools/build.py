#!/usr/bin/env python3
"""Build the package zips, `dist/index.json` and the catalogue page `site/index.html`.

    python tools/build.py [--template <template checkout>]

For every `packages/<id>/` this reads the header of `package.md`, writes `dist/<id>-<version>.zip` (the package
root at the zip root, sorted names, fixed timestamps, so a second run gives the same bytes), then `dist/index.json`
(per package: version, zip, sig, `contents`, `tools`, `stack` where the header has one, `red` where
`maintainers/red.json` names the package) and `site/index.html`. With `--template` each package is first checked by that template's `packages.py plan`, run
in a throwaway copy of the template's `.act/` folder; a refusal stops the build and prints the reasons.
This tool never signs; the maintainers sign each zip afterwards.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
REQUIRED = ("id", "version", "requires-template", "tools", "license", "contains-code")
PLAN_TIMEOUT = 120


class BuildError(Exception):
    """A package that cannot be built; the message names the package and the reason."""


def read_package(folder: Path) -> Dict[str, object]:
    """Header fields and the Contents text of `<folder>/package.md`."""
    path = folder / "package.md"
    if not path.is_file():
        raise BuildError(f"{folder.name}: no package.md")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise BuildError(f"{folder.name}: package.md is not valid UTF-8 ({error.reason} at byte {error.start})") from error
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise BuildError(f"{folder.name}: package.md does not start with a --- header")
    header: Dict[str, str] = {}
    end = None
    for number, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = number
            break
        if ":" in line:
            key, _, value = line.partition(":")
            header[key.strip()] = value.strip()
    if end is None:
        raise BuildError(f"{folder.name}: package.md header is not closed by ---")
    for key in REQUIRED:
        if not header.get(key):
            raise BuildError(f"{folder.name}: header field `{key}` is missing or empty")
    if not ID_RE.match(header["id"]) or header["id"] != folder.name:
        raise BuildError(f"{folder.name}: header id `{header['id']}` must be a valid id equal to the folder name")
    if not VERSION_RE.match(header["version"]):
        raise BuildError(f"{folder.name}: version `{header['version']}` is not X.Y.Z")
    contents: List[str] = []
    inside = False
    for line in lines[end + 1:]:
        if line.startswith("## "):
            inside = line[3:].strip() == "Contents"
            continue
        if inside:
            contents.append(line)
    return {
        "id": header["id"],
        "version": header["version"],
        "requires": header["requires-template"],
        "tools": [tool.strip() for tool in header["tools"].split(",") if tool.strip()],
        "stack": [item.strip() for item in header.get("stack", "").split(",") if item.strip()],
        "license": header["license"],
        "code": header["contains-code"],
        "contents": " ".join(" ".join(contents).split()),
        "contents_text": "\n".join(line.rstrip() for line in contents).strip("\n"),
    }


def package_files(folder: Path) -> List[Path]:
    """Every file of the package, sorted by its posix path; caches are left out."""
    files = [p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    return sorted(files, key=lambda p: p.relative_to(folder).as_posix())


def build_zip(folder: Path, target: Path) -> None:
    """Write the zip with sorted entries, fixed timestamps and fixed attributes."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in package_files(folder):
            info = zipfile.ZipInfo(path.relative_to(folder).as_posix(), ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def check_with_template(template: Path, folders: List[Path]) -> List[str]:
    """Run the template's `packages.py plan` on each folder inside a throwaway copy of its `.act/`; return problems."""
    script = template / ".act" / "scripts" / "packages.py"
    if not script.is_file():
        raise BuildError(f"--template {template}: no .act/scripts/packages.py")
    problems: List[str] = []
    with tempfile.TemporaryDirectory(prefix="act-packages-build-") as work:
        project = Path(work) / "project"
        shutil.copytree(template / ".act", project / ".act", ignore=shutil.ignore_patterns("__pycache__"))
        config = template / "docs" / "ai" / "config.md"
        if config.is_file():
            (project / "docs" / "ai").mkdir(parents=True)
            shutil.copy2(config, project / "docs" / "ai" / "config.md")
        for folder in folders:
            try:
                done = subprocess.run([sys.executable, str(project / ".act" / "scripts" / "packages.py"), "plan",
                                       str(folder)], cwd=project, stdin=subprocess.DEVNULL, capture_output=True,
                                      text=True, encoding="utf-8", errors="replace", timeout=PLAN_TIMEOUT)
            except subprocess.TimeoutExpired:
                problems.append(f"{folder.name}: plan ran past {PLAN_TIMEOUT} seconds")
                continue
            if done.returncode != 0:
                reasons = (done.stdout + done.stderr).strip()
                problems.append(f"{folder.name}: the template refuses this package:\n{reasons}")
    return problems


def load_red() -> Dict[str, str]:
    """`maintainers/red.json`: `{"<id>": "<reason>"}`."""
    path = ROOT / "maintainers" / "red.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise BuildError(f"maintainers/red.json: {error}") from error
    if not isinstance(data, dict):
        raise BuildError(f"maintainers/red.json must be an object of {{\"<id>\": \"<reason>\"}}, "
                         f"not {type(data).__name__}")
    for key, value in data.items():
        if not isinstance(value, str) or not value.strip():
            raise BuildError(f"maintainers/red.json: the reason for {key!r} must be a non-empty string, "
                             f"not {value!r}")
    return data


def index_entry(info: Dict[str, object], zip_name: str, red: Dict[str, str]) -> Dict[str, object]:
    """One entry of `dist/index.json`: what `fetch` needs, then the optional fields a reader gets. A field the package
    does not have (no Contents text, no `stack` header, not red) is left out, never written empty."""
    entry: Dict[str, object] = {"version": str(info["version"]), "zip": zip_name, "sig": f"{zip_name}.sig"}
    if info["contents_text"]:
        entry["contents"] = info["contents_text"]
    if info["tools"]:
        entry["tools"] = info["tools"]
    if info["stack"]:
        entry["stack"] = info["stack"]
    reason = red.get(str(info["id"]))
    if reason is not None:
        entry["red"] = reason
    return entry


def render_site(packages: List[Dict[str, object]], red: Dict[str, str]) -> str:
    """The catalogue page: plain HTML and CSS, no external resources."""
    esc = html.escape
    cards: List[str] = []
    for pkg in packages:
        reason = red.get(str(pkg["id"]))
        mark = f'<p class="red">RED: {esc(reason)}</p>' if reason is not None else ""
        cards.append(
            f'<section class="pkg{" is-red" if reason is not None else ""}" id="{esc(str(pkg["id"]))}">'
            f'<h2>{esc(str(pkg["id"]))} <small>{esc(str(pkg["version"]))}</small></h2>{mark}'
            f'<p>{esc(str(pkg["contents"]))}</p>'
            "<dl>"
            f'<dt>Tools</dt><dd>{esc(", ".join(pkg["tools"]))}</dd>'  # type: ignore[arg-type]
            f'<dt>License</dt><dd>{esc(str(pkg["license"]))}</dd>'
            f'<dt>Contains code</dt><dd>{esc(str(pkg["code"]))}</dd>'
            f'<dt>Requires template</dt><dd>{esc(str(pkg["requires"]))}</dd>'
            "</dl>"
            f'<p><code>python .act/scripts/packages.py fetch {esc(str(pkg["id"]))}</code></p>'
            "</section>"
        )
    body = "\n".join(cards) if cards else "<p>No packages yet.</p>"
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>act packages</title>\n<style>\n"
        "body{font-family:sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;line-height:1.5}\n"
        ".pkg{border:1px solid #ccc;border-radius:6px;padding:.5rem 1rem;margin:1rem 0}\n"
        ".pkg.is-red{border-color:#b00020}\n.red{color:#b00020;font-weight:bold}\n"
        "dl{display:grid;grid-template-columns:max-content 1fr;gap:.2rem 1rem}dt{font-weight:bold}dd{margin:0}\n"
        "small{color:#555}\n"
        "</style>\n</head>\n<body>\n<h1>act packages</h1>\n"
        "<p>Packages for the agentic coding template, from template v2.7.0 on. Fetch one with "
        "<code>packages.py fetch &lt;id&gt;</code>, then read the plan from <code>packages.py add &lt;id&gt;</code> "
        "before you say yes.</p>\n"
        "<p>More: <a href=\"https://github.com/wrufeger/agentic-coding-template\">the template</a> · "
        "<a href=\"https://wrufeger.github.io/agentic-coding-template-docs/packages/\">"
        "packages on the documentation site</a> · "
        "<a href=\"https://wrufeger.github.io/agentic-coding-template-docs/guides/packages/\">"
        "guide: using, creating and submitting packages</a> · "
        "<a href=\"https://github.com/wrufeger/act-packages\">package repository</a></p>\n"
        f"{body}\n</body>\n</html>\n"
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build package zips, dist/index.json and site/index.html.")
    parser.add_argument("--template", help="a template checkout: run its packages.py plan on every package first")
    args = parser.parse_args(argv)
    try:
        folders = sorted(p for p in (ROOT / "packages").iterdir() if p.is_dir()) if (ROOT / "packages").is_dir() else []
        infos = [read_package(folder) for folder in folders]
        if args.template:
            problems = check_with_template(Path(args.template).resolve(), folders)
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
        red = load_red()
        unknown = sorted(set(red) - {str(i["id"]) for i in infos})
        if unknown:
            raise BuildError(f"maintainers/red.json names packages that do not exist: {', '.join(unknown)}")
    except (BuildError, OSError, ValueError) as error:
        print(f"build: {error}", file=sys.stderr)
        return 1
    dist = ROOT / "dist"
    index: Dict[str, Dict[str, object]] = {}
    target = dist
    try:
        dist.mkdir(exist_ok=True)
        for folder, info in zip(folders, infos):
            name = f"{info['id']}-{info['version']}.zip"
            target = dist / name
            build_zip(folder, target)
            index[str(info["id"])] = index_entry(info, name, red)
            print(f"built dist/{name}")
        target = dist / "index.json"
        write_text(target, json.dumps({"packages": index}, indent=2, sort_keys=True) + "\n")
        target = ROOT / "site" / "index.html"
        write_text(target, render_site(infos, red))
    except OSError as error:
        print(f"build: cannot write {target}: {error}", file=sys.stderr)
        return 1
    print(f"wrote dist/index.json and site/index.html ({len(infos)} packages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
