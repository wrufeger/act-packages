# act-packages

Packages for the agentic coding template ("act"). A package brings rules, coding sets, skills, roles, topics, scripts
and check modules into a project that runs on the template, without changing the template itself.

## Getting a package

In a project on the template, either ask the assistant with the `/act-packages` skill, or run the steps yourself:

```
python .act/scripts/packages.py fetch <id>              # downloads <id>-<version>.zip and its .sig, activates nothing
python .act/scripts/packages.py index                   # what this repository offers, from its index.json
python .act/scripts/packages.py add <id>                # dry run: plan, origin and a diff of every file that changes
python .act/scripts/packages.py add <id> --yes <code>   # after you said yes to that plan
python .act/scripts/packages.py list                    # what is active, what rests, what is broken
python .act/scripts/packages.py remove <id>             # the same in reverse; --yes <id> carries it out
```

`add` never installs in the same step it shows the plan: the code in `--yes <code>` belongs to the exact bytes of the
plan you saw.

## Catalogue

The catalogue is the Pages site of this repository, built by `tools/build.py` from `packages/`: one entry per package
with version, contents, tools, license, whether it contains code, the template version it needs and a red mark with a
reason when the maintainers list one (`maintainers/red.json`). Nothing else marks a package red.

The same facts are in `dist/index.json`, which `packages.py index` and `packages.py fetch` read. Per package it holds
`version`, `zip` and `sig` (what `fetch` needs) and, where the package has them, `contents` (the text of its
`## Contents` section), `tools`, `stack` (the optional `stack` field of the `package.md` header, a comma list) and
`red` (the reason from `maintainers/red.json`). A field a package does not have is left out. The file is the same
bytes on every build of the same sources.

## Trust

Zips are signed by the template author; the project checks the signature against `.act/package-signers` and, if it
exists, its own `docs/ai/local/package-signers` (for a key the project trusts on its own). An unsigned
package is only admitted with `packages-unverified: scan` or `allow` in `docs/ai/config.md`, and a signature that does
not verify is refused in every mode. A package's code (`install.py`, check modules) is trusted code once installed:
read the plan and, for unsigned packages, the scan findings before you say yes.

## Repository layout

| Path | Holds |
| :--- | :--- |
| `packages/<id>/` | one package each; `packages/example/` is a small one to learn from |
| `docs/creating-a-package.md` | how to write a package |
| `maintainers/red.json` | hand-kept `{"<id>": "<reason>"}` list of packages the catalogue marks red |
| `tools/build.py` | builds `dist/<id>-<version>.zip`, `dist/index.json` and `site/index.html` |
| `tests/` | tests of the package code (`install.py`, check modules): `python -B -m unittest discover -s tests -t .` |

Build: `python tools/build.py [--template <path to a template checkout>]`. With `--template` every package is first
checked by that template's `packages.py plan`, and a refusal stops the build with the reasons. `dist/` and `site/` are
not committed; they are published as release assets and as the Pages site.

## Signing

`build.py` never signs. After a build, the maintainers sign each zip with `ssh-keygen -Y sign -n act-package` (the form
the template checks, `.act/formats/package.md`) and publish the zips, the `.sig` files and `index.json` as release
assets.

## Releases

Projects fetch from `https://github.com/wrufeger/act-packages/releases/latest/download/`, which reaches only the
assets of the release GitHub marks as latest. So every release:

- is a full release, never a draft or pre-release;
- carries `index.json` and the zip and `.sig` of every package and version that `index.json` lists, not only the ones
  that changed;
- is tagged with its date, `YYYY-MM-DD`, and `YYYY-MM-DD.2` and so on for a second release on the same day.

The Pages site is the content of `site/` on the branch `gh-pages` (root folder), replaced on every release.

## Contributing

Open a pull request that adds or changes `packages/<id>/`; see `docs/creating-a-package.md`. A package is licensed by
the `license` field of its `package.md`; the repository itself is MIT (`LICENSE`).
