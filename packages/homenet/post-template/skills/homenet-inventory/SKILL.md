---
name: homenet-inventory
description: Use when the network has not been inventoried yet, or when the docs under docs/project/homenet/ should be checked against the live state. Ends with one file per area, each with a "data as of" line, and a list of the deviations found.
---

# Inventory the network and audit its docs

Result: one Markdown file per area under `docs/project/homenet/`, each with a "data as of" line, plus the table of
deviations between the docs and the live state. The orchestrator runs this skill; the readers only read.

1. **Check the ground.** `docs/project/homenet/access.md` must exist and name, for every system to be read, a way and
   the role `homenet-reader` (`R-homenet-access`). A system without a row is not read: it goes to the owner as a todo
   (`R-homenet-handoff`) and is left out of this run. Read the existing files in `docs/project/homenet/` and note
   their "data as of" lines.
2. **Cut the areas.** Network (router, controller, switches, access points, DNS filter), servers and hypervisor
   (hosts, virtual machines, containers, single-board computers), devices (everything that connects), and Home
   Assistant only when the setting `homenet-home-assistant` is `yes`. A small network may merge areas; one reader
   never gets more than one area.
3. **Start one `homenet-reader` per area, in parallel.** A reader starts no further worker. The assignment names the
   area, the rows of the table it may use, the existing file for that area and the fields wanted per device: name,
   area (room or zone), model, firmware, network (segment, address or reservation, DNS name), protocol, purpose, data
   as of. SSH only as one bundled call per host, read commands only (`R-homenet-ssh`); no scan of any kind
   (`R-homenet-never`). For Home Assistant the reader lists integrations and the areas they cover and points to the
   entities; it does not copy them, because Home Assistant stays their source.
4. **Collect the answers.** Each reader returns a deviation table (place, doc, live, source) and corrected or new doc
   lines as text. A reader that hit a refusal, a missing row or a login in a browser says so; each of these becomes
   a todo for the owner with the exact steps (`R-homenet-handoff`). Nothing is retried under another wording.
5. **Settle the deviations with the owner.** Show the combined table. Where docs and live state differ, the live state
   is the proposal; the owner decides when the docs hold an intention (a planned name, a reserved address). Open
   points stay open and are listed.
6. **Write the files.** The orchestrator writes one file per area in the project's `language-docs`, each with a line
   "data as of <date>" near the top. Existing files are only added to and corrected line by line, never replaced as a whole.
   Use a table or list per device; YAML only for something that is computed from the data. Secret values, keys and
   export contents never appear (`R-homenet-exports`); where a value would be one, write where it lives instead.
7. **Name each file in `docs/project/homenet/README.md`** with one line and its state, and add the DNS names with
   where they apply (`R-homenet-names`). Add a journal line.
8. **Cross-check the sample.** Start one `homenet-reader` per changed area again on a handful of lines, chosen at
   random, and compare them with what was written. A difference goes back to step 5.

Done when every area has its file with a current "data as of" line, the README names each file, every deviation is
resolved or listed as open with an owner, no system outside the rights table was touched, and the sample of step 8
matched.
