# Setting up homenet

For the main session, after the owner said yes to the install plan. Work through the steps in order; each ends with
a check. Only add, never overwrite: a file or entry that exists is extended, not replaced. Everything written into the
project under `docs/project/homenet/` is in the project's `language-docs` (the scaffolds below are written in that
language as they are written). The assistant never reads a secret file or `~/.ssh`. A login in a browser (OAuth)
stops the setup at that step with a todo for the owner (`R-homenet-handoff`); the setup goes on after it.

## 1. Read the report of `install.py`

- Assistant: reads the report that the installer printed (Python version, `ssh` with its version line, `ping`, and on
  Windows whether `python` or `python3` is the store alias and whether `py` exists). It changes nothing yet.
- Owner: takes note of what is missing; installs a missing `ssh` client, or turns off the store alias in the system
  settings, themselves.
- Check: every line of the report is understood and each missing tool is either fixed or noted as a limit (no `ssh` =
  no SSH steps below). A line "could not check: timed out" means that tool did not answer in time: check it by hand;
  nothing was decided. A non-zero exit of `install.py` leaves the package installed; its message names
  `packages.py remove homenet` for the owner who wants it gone.

## 2. Settings

- Assistant: the question `homenet-home-assistant` comes from the package flow (`packages.py settings homenet`); the
  assistant asks it once and stores the answer there.
- Owner: answers yes or no.
- Check: `packages.py settings homenet` shows an answer for the key.

## 3. Secrets

- Assistant: names the variables the MCP entries and scripts need (one per service, for example
  `<HA_TOKEN_VARIABLE>`), and says in which environment Claude Code must be started so that it sees them. It does
  not ask for a value and never reads the file or variable.
- Owner: creates a gitignored secret file or sets the environment variables, with read-only accounts or tokens where
  the product allows one, and restarts Claude Code from that environment.
- Check: the owner confirms that the variables are set; the assistant tests nothing yet. The secret file is listed in
  `.gitignore` (the assistant looks at that file, not at the secret).

## 4. MCP entries and one read test per service

- Assistant: proposes one entry per service the owner uses, from the section "MCP and API catalogue" at the end of this file, with the token as
  `${<VARIABLE>}` and the address as a DNS name. It writes `.mcp.json` only after the owner's yes (`R-safe-git-metadata`
  covers that file for workers; the main session writes it), never with a literal token. For each server it lists the
  server's own tools with the owner and writes the names of tools that only read, per server, into the project file
  `docs/project/homenet/mcp.md` (scaffold below); the installed copy of `topics/homenet-mcp.md` is never edited, it is
  hash-checked against the lock. After the owner's yes it extends the `tools` line of
  `.claude/agents/homenet-reader.md` with those names (a role copy a person edited is never overwritten). The read
  calls of this step belong to this setup; they are entered in the rights table in step 6.

  Scaffold of `docs/project/homenet/mcp.md` (in the project's `language-docs`; the example is invented):

```
# MCP read tools

Tools that only read, per server, chosen with the owner from the server's own tool list. Source of the entries:
`.act-local/packages/homenet/install.md` § "MCP and API catalogue".

| Server (entry id) | Read tools | Chosen on |
| :--- | :--- | :--- |
| homenet-ha | `<tool-name>`, `<tool-name>` | <date> |
```

- Owner: says yes or no per entry; sets the server up on its side (for Home Assistant, switches on its MCP
  integration; for each, a read-only user).
- Check: one read call per service returns data. A failure is reported with its cause, not retried by other means.

## 5. SSH, as a recipe for the owner

- Assistant: gives the recipe below as a todo, per host, and does not touch `~/.ssh`. The login tests of this step are
  read calls that belong to this setup; they are entered in the rights table in step 6.
- Owner: creates a key for the network work, installs its public half on each host, adds the host entries and tests
  one login by hand. Add to the SSH configuration file:

```
Host <host-alias>
    HostName <host>.example
    User <user>
    IdentityFile ~/.ssh/<key-file>
    StrictHostKeyChecking accept-new
    ControlMaster auto
    ControlPath ~/.ssh/cm-%C
    ControlPersist 60
```

  Notes: `accept-new` records a first host key and refuses a changed one; never `no`. The three `Control` lines are
  optional connection sharing, which makes a bundle of commands cheaper (on Windows the OpenSSH client may lack it:
  leave those lines out). The first key of a new host is compared by the owner over a second way (console, web
  interface) where one exists (`R-homenet-ssh`).
- Check: per host, one bundled read-only call (for example `ssh <host-alias> 'uname -a; uptime'`) returns output. One
  connection, several commands.

## 6. The rights table

- Assistant: creates `docs/project/homenet/access.md` from the scaffold below, fills the rows with the owner from
  steps 4 and 5, and asks what each credential can technically do. A standing approval is entered only when the owner
  says so in this session, with the date and the name of the owner as approver. Where a credential can do more than is
  approved, the row says that the way is used only through a script that knows the approved methods.
- Owner: states what each system may be used for, and for which action classes a standing approval is wanted.
- Check: every system and way in use has a row; each approved entry has a date and an approver; each system has a
  backup location.

  Scaffold (the example row is invented and is deleted or replaced during the setup):

```
# Rights table

One row per system, way and role (`R-homenet-access`). A standing approval is a dated entry for a named action
class in the column "approved", written only on the owner's word.

| System | Way | Role | Technically possible | Approved | Backup location | Workstation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| nas.example (example) | SSH | homenet-reader | read and write of the whole system | read commands (2026-01-15, owner) | `<backup-share>/nas.example/` | - |
```

## 7. First inventory

- Assistant: runs the skill `homenet-inventory` with the readers it describes, and writes the area files from the
  scaffold below.
- Owner: settles the deviations the skill shows and names what is only planned.
- Check: one file per area exists, each with a "data as of" line; the sample cross-check of the skill matched.

  Scaffold of an area file:

```
# <Area>

Data as of: <date>

| Name | Area | Model | Firmware | Network | Protocol | Purpose | Data as of |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| pi.example (example) | utility room | <model> | <version> | 198.51.100.10, name `pi.example` | Ethernet | DNS filter | <date> |
```

## 8. Doc structure

- Assistant: writes `docs/project/homenet/README.md` naming `access.md`, `mcp.md` and each area file in one line with its
  state, and the DNS names with where each applies (`R-homenet-names`). It adds the folder with its README to
  `docs/README.md` where that file lists folders.
- Owner: reads the README.
- Check: every file in `docs/project/homenet/` is named in the README; nothing contains a secret, a key or the
  content of an export (`R-homenet-exports`).

## MCP and API catalogue

Entries in the form of the template's MCP catalogue (`.act/mcp-catalog.md`, "How to read an entry"); `read-tools` stays empty here, the filled lists go into `docs/project/homenet/mcp.md`.

## homenet-ha

- id: `homenet-ha`
- name: Home Assistant, its own MCP server integration
- serves: smart-home
- purpose: read states, areas and devices of Home Assistant; the integration can also call services, which is a write
- suggest-when: `homenet-home-assistant` is `yes`
- transport: http
- auth: token, url
- options: `<ha-host>` (url: the instance by its DNS name), `<HA_TOKEN_VARIABLE>` (token: a long-lived access token of a dedicated user, in the environment)
- claude-command: `claude mcp add-json --scope project homenet-ha '{"type":"http","url":"https://<ha-host>/<mcp-path>","headers":{"Authorization":"Bearer ${<HA_TOKEN_VARIABLE>}"}}'`
- claude-json: see block
- notes: the integration has to be switched on in Home Assistant first; take `<mcp-path>` from its documentation (unverified). Which entities it exposes is set there: expose only what the work needs. A token may be able to call services; if so, use it only through the rights table. Without a read-only way, read through the API with a script that knows only read methods.
- read-tools:
- source: unverified (the product's documentation)
- checked: unchecked

```json
{"mcpServers": {"homenet-ha": {"type": "http", "url": "https://<ha-host>/<mcp-path>",
  "headers": {"Authorization": "Bearer ${<HA_TOKEN_VARIABLE>}"}}}}
```

## homenet-controller

- id: `homenet-controller`
- name: network controller (REST API with a local read-only user)
- serves: network
- purpose: list devices, clients, ports, access points and their state from the controller
- suggest-when: a network controller manages the switches or access points
- transport: http
- auth: username-password, url
- options: `<controller-host>` (url: by DNS name), a local user with a read-only role (username and password in the environment as `${<CONTROLLER_USER_VARIABLE>}` and `${<CONTROLLER_PASSWORD_VARIABLE>}`, never an owner's account)
- claude-command: none (no ready MCP server is assumed; the access is a script in the project that calls the REST API with the credential from the environment)
- claude-json: none
- notes: a key that can write is used only through a script that knows the approved methods (`R-homenet-access`); no direct call with that credential. Firewall, VLAN and WLAN changes here are never approved by a standing entry (`R-homenet-never`). Exports of the controller carry WLAN and VPN keys (`R-homenet-exports`).
- read-tools:
- source: unverified (the controller's API documentation)
- checked: unchecked

## homenet-hypervisor

- id: `homenet-hypervisor`
- name: hypervisor (API token with a read-only role)
- serves: virtualization
- purpose: list hosts, virtual machines, containers, storage and their state; read backup status
- suggest-when: a hypervisor runs the servers
- transport: http
- auth: token, url
- options: `<hypervisor-host>` (url: by DNS name), `<HYPERVISOR_TOKEN_VARIABLE>` (token: an API token bound to a role that may only audit, in the environment)
- claude-command: none (a script in the project, or the hypervisor's own MCP server where one exists and its read tools can be told apart)
- claude-json: none
- notes: starting, stopping or restarting a machine is a write and a restart, covered only by a dated entry in the table or a dated approval for the case; deleting a machine or a snapshot is never approved by a standing entry. A backup tool of the hypervisor is used only to create backups.
- read-tools:
- source: unverified (the hypervisor's API documentation)
- checked: unchecked

## homenet-monitoring

- id: `homenet-monitoring`
- name: Grafana, its own MCP server
- serves: monitoring
- purpose: read dashboards, data sources and queries; find what a dashboard shows before something is renamed
- suggest-when: Grafana shows the network's or the house's data
- transport: stdio
- auth: token, url
- options: `<grafana-host>` (url: by DNS name), `<GRAFANA_TOKEN_VARIABLE>` (token: a service account token with the viewer role, in the environment)
- claude-command: `claude mcp add --scope project --transport stdio homenet-monitoring -- <grafana-mcp-command>` (host and token go in through the `env` block of the JSON below, or are passed with the command's `--env` option; never as a value in the command)
- claude-json: see block
- notes: take command, arguments and the names of the variables from the server's own documentation (unverified); pass the host and the token by environment, not by argument. A viewer token cannot write dashboards; a change to a dashboard needs another way and the rights table.
- read-tools:
- source: unverified (Grafana's documentation)
- checked: unchecked

```json
{"mcpServers": {"homenet-monitoring": {"command": "<grafana-mcp-command>", "args": [],
  "env": {"GRAFANA_URL": "https://<grafana-host>", "GRAFANA_TOKEN": "${<GRAFANA_TOKEN_VARIABLE>}"}}}}
```

## homenet-nas

- id: `homenet-nas`
- name: NAS, the vendor's MCP server
- serves: storage
- purpose: read shares, volumes, disk health and backup jobs of the NAS
- suggest-when: a NAS holds data or backups and its vendor offers an MCP server
- transport: http
- auth: token, url
- options: `<nas-host>` (url: by DNS name), `<NAS_TOKEN_VARIABLE>` (token: of a user with read rights only, in the environment)
- claude-command: none (depends on the vendor; take it from its documentation)
- claude-json: none
- notes: read tools only; a tool that also writes, for example for backups, is listed only where its read action can be used alone. The NAS's internal storage and databases are hard core (`R-homenet-never`): read only with a dated approval for the exact case.
- read-tools:
- source: unverified (the vendor's documentation)
- checked: unchecked
