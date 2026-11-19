---
id: homenet
version: 0.1.0
requires-template: >=2.6.0
tools: claude-code
license: MIT
contains-code: yes
---

# homenet — home network administration

## Contents

Rules, roles and skills for running a home network or homelab from a project on the template: LAN and WLAN, router
and network controller, hypervisor, Raspberry Pi and other servers, DNS filter, devices, firewall and Home Assistant.
The package carries no network data (no addresses, host names or credentials); the setup records them in the project
under `docs/project/homenet/`. It builds on `R-safe-approval` and `.act/rules/topics/live-systems.md` and repeats
neither.

- Rules: `R-homenet-access` (a rights table per system and way; a dated entry there is the standing approval for a
  named action class), `R-homenet-never` (the hard core no standing approval covers), `R-homenet-ssh`,
  `R-homenet-rename`, `R-homenet-names`, `R-homenet-exports`, `R-homenet-handoff`; an extension of `R-safe-approval`
  that points to the rights table.
- Roles: `homenet-reader` (reads only, never scans, cross-checks every write over its own way) and `homenet-writer`
  (backs up first, never deletes, a write is done only after the reader's cross-check).
- Skills: `homenet-inventory` (first inventory and doc audit against the live state) and `homenet-add-device`.
- Topic: `homenet-mcp` (MCP servers and APIs for Home Assistant, network controller, hypervisor, monitoring and NAS,
  with read and write kept apart).
- Code: `install.py` only reports which tools are there (`ssh`, Python, interpreter traps on Windows); it opens no
  connection and writes nothing. The check module `homenet_no_scan` refuses port scanners (`nmap`, `masscan`, `zmap`
  and similar, `nc -z` over more than one port) in shell calls of Claude Code.

## settings

- homenet-home-assistant: Is Home Assistant part of this network (yes or no)?
