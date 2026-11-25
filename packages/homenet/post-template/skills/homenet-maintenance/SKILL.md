---
name: homenet-maintenance
description: Use when recurring home network upkeep may be due (version checks, device audits) or the owner asks what is due. Shows what the status files under docs/project/homenet/maintenance/ call due, runs only that, and ends with a dated report and follow-up work as a list.
---

# Recurring home network maintenance

Result: the due tasks are done, each with a dated report under `docs/project/homenet/maintenance/reports/` and its
status file brought forward; follow-up work comes back as a list. The orchestrator runs this skill. It changes nothing
on the systems and starts no worker.

1. **Show what is due.** Run the installed script and show its output as it is: `python
   .act-local/packages/homenet/post-template/scripts/homenet_due.py` from the project root (`packages.py add` leaves
   it there). Options: `--root <folder>` (project root, default the current folder), `--today YYYY-MM-DD` (pretend
   today is that day), `--check` (names every broken status file with its reason), `--hash <task>` (prints the
   current trigger hash of a task). The script prints at most five lines and nothing when nothing is due. Exit codes:
   the default mode is always silent on a problem and exits 0, also with a bad `--today`; `--check` exits 1 when a
   status file is broken; `--hash` exits 1 for an unknown task, a broken one or one without a trigger. No output
   means there is nothing to do: say so and stop.
2. **Pick what to run.** Only what the output names, unless the owner names another task. A broken status file is
   checked with `--check` and goes to the owner; it is not guessed at.
3. **Run each task by its status file.** The file `docs/project/homenet/maintenance/<task>.md` says what the task is
   and which tables, areas or tools it reads. Reading goes through the rows of the rights table
   (`R-homenet-access`); a system without a row is left out and becomes an owner todo (`R-homenet-handoff`). The run
   reads, counts and compares; it changes nothing, deletes nothing, and starts no worker (the orchestrator reads
   itself). Nothing here is a write: a needed change goes into the follow-up list.
4. **Write the report** `docs/project/homenet/maintenance/reports/<YYYY-MM-DD>-<task>.md` in the project's
   `language-docs`: what was checked, what was found, counted rather than listed. No personal data and no content of an
   export (`R-homenet-exports`); where a value would be one, write where it lives.
5. **Bring the status file forward.** After the work is done, write `last` (today), `next` (today plus `interval`, only
   for a task with `interval`) and `trigger-hash` (the output of `homenet_due.py --hash <task>`, only for a task with
   `trigger`) into the status file. A run that failed leaves the file as it is.
6. **Return follow-up work as a list**: one line per item, with the task, what is to be done and which role or owner
   step it needs. Add a journal line.

## Status file

One file per task, `docs/project/homenet/maintenance/<task>.md`. It starts with a header block between two `---`
lines (the script requires it), then the task's description:

```
---
interval: 4w
last: 2026-10-27
next: 2026-11-24
trigger: docs/project/homenet/*.md
trigger-hash: <hash>
---
```

- `last`: always; the date of the last run, or `never`.
- `interval`: `<n>d` or `<n>w`; left out for a task that runs only on a trigger.
- `next`: the date from which it is due; required with `interval`, optional without.
- `trigger`: a glob relative to the project. With `trigger`, `trigger-hash` is required: the hash of the matching files
  at the last run. Files under `docs/project/homenet/maintenance/` and files outside the project never count for the
  hash. A trigger with a root, a drive, `..` or `**` not as a whole path part makes the status file broken.
- A new task starts with `last: never` and, with a trigger, `trigger-hash: none`.

A task is due when `last` is `never`, when a set `next` is today or earlier, or when the hash of the trigger files
differs from `trigger-hash`; a task with only a trigger is due on exactly those grounds, without `next`.

Examples of a status file: a version check (compare the versions of the systems named in the docs with what the
vendors list; interval) and a device audit (compare the device files with the live state, as the first inventory
does; interval or a trigger on the device files). The package ships none: the owner and the assistant write them when
a task is wanted.

Done when every due task has its report and its status file shows the new `last` (and `next` and hash where the task
has them), and the follow-up list is handed over.
