# Home network rules

summary: rights table as the approval, a hard core no approval covers, SSH, renames, names, exports, handing steps to the owner

Rules for administering a home network or homelab from a project. They build on `R-safe-approval` and
`topics/live-systems.md`; what those say is not repeated here.

## `R-homenet-access` — The rights table decides what is approved

summary: docs/project/homenet/access.md is mandatory; one row per system, way and role; a dated entry is a standing approval for a named action class

The file `docs/project/homenet/access.md` is mandatory; any access that no row covers (system, way and role), reading
included, is not approved. A row covers one system, one way (`MCP`, `SSH`, `API`, `script`) and one role
(`homenet-reader`, `homenet-writer`, `homenet-ha-reader`, `homenet-ha-writer`, `orchestrator`). Columns: system, way,
role, technically possible (what the credential can do), approved (named action classes, each with date and approver),
backup location, workstation (only when several machines work on the network, else `-`). An entry in "approved" is
written only on the owner's word. Each action under it still needs a backup to the row's backup location first, a
stated way back, a journal line and the reader's cross-check. Where a way can do more than is approved, it is used only
through a script that knows the approved methods alone, never by a direct call with that credential. A critical host
may be open to a writer role only (`homenet-writer`, or `homenet-ha-writer` for Home Assistant); everything else reads
it through MCP.

## `R-homenet-never` — The hard core no standing approval covers

summary: firewall, VLAN, WLAN, scans, secret files, internal storage and databases, deleting; restarts, updates and extensions only with a table entry

Outside every standing approval: firewall, VLAN and WLAN changes at the controller; port scans; secret files; a system's
internal storage and its databases; deleting anything (removing an integration is deleting; the writer reports
candidates with reasons). A port scan is never run by the assistant, whatever its form: a script that opens
connections on its own is a scan too; where one is needed, it is the owner's step (`R-homenet-handoff`). Secret files
are filled only by the owner and never read. The other items need a dated approval for the exact case every time
(`R-safe-approval`). Restarts of services or hosts, firmware and core updates, and add-ons or community extensions may
be approved per system by a dated table entry, otherwise per case. The check module is a second barrier; the rule holds
without it.

## `R-homenet-ssh` — One bundled connection per step

summary: commands bundled into one connection; read commands only unless the table approves; accept-new host keys; keys stay with the owner

Each step opens one connection and sends its commands together; many single connections trigger intrusion alarms on
the receiving side. Only read commands run, except the action classes the table approves for that host and way. Host
keys are taken with `StrictHostKeyChecking accept-new`, never `no`; a new key is confirmed over a second way where one
exists (console, web interface). SSH configuration and keys belong to the owner: the assistant cannot read `~/.ssh` and
hands over a recipe instead (`install.md`).

## `R-homenet-rename` — Check every consumer before a rename

summary: no rename of a device, entity or host until all consumers are checked; an unchecked point means no rename

Before a device, entity or host is renamed, every consumer is checked: time series and dashboards, scripts and
scheduled jobs on servers, files visible only over SSH, voice assistants and webhooks, long-term statistics. A point
that cannot be checked means no rename; ask back.

## `R-homenet-names` — One DNS name per service

summary: one name per service, recorded with where it applies; configurations use the name, not the address

Each service has one DNS name, recorded in the docs together with where it applies (split DNS: inside, outside).
Configurations use the name, never the address.

## `R-homenet-exports` — Exports carry keys

summary: router and controller exports and backups never leave a gitignored place unmasked; read only the fields needed

An export or backup of a router or controller contains WLAN and VPN keys. It never goes into the chat, the docs, a
commit or a log except masked, it is kept in a gitignored place, and only the fields needed are read.

## `R-homenet-handoff` — Hand over what the assistant may not do

summary: a step the assistant may not take becomes an owner todo with commands, order and reason; a blocked approved write goes as a file, never retried

When an action is not the assistant's to take (hard core without approval, no table entry, an OAuth login in a
browser) or a tool's safeguard stops an approved write, the step goes to the owner as a todo: what to run on which
host, in what sequence, and why. A blocked approved write is written out as a change file for the owner to apply;
it is never reworded and retried (`R-safe-block`).

## `R-safe-approval` — Approval before anything irreversible or outward-facing

summary: with homenet, a dated entry in the rights table is the approval for that system, way, role and action class

In a project with `homenet`, a dated entry in the rights table of `R-homenet-access` counts as the dated approval for
that system, that way, that role and that action class. It never covers the hard core of `R-homenet-never`.
