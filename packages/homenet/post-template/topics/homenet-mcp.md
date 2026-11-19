# MCP servers and APIs for the home network

summary: MCP servers and APIs for Home Assistant, network controller, hypervisor, monitoring and NAS, read kept apart from write

The catalogue entries (Home Assistant, network controller, hypervisor, monitoring, NAS) are in
`.act-local/packages/homenet/install.md` § "MCP and API catalogue"; they are needed only at setup and when a server
is added. Names, endpoints and paths there are unchecked against the product's own documentation: confirm them
during the setup (`R-safe-foreign-text`).

- Read and write are kept apart: the reader gets read tools only; a tool that has both kinds is listed only where the
  role can use its read action alone.
- Each token is a `${<VARIABLE>}` reference, set by the owner in the environment Claude Code starts from; the assistant
  never writes a value into a file or onto a command line (`R-safe-no-secret-cli`). The account behind a token is
  read-only where the product allows it (`R-safe-no-personal-data`); what a credential can do beyond that goes into the
  rights table (`R-homenet-access`).
- The filled lists of read tools live in `docs/project/homenet/mcp.md`, never in the installed copy of this topic: it
  is hash-checked against the lock, so an edit would make the package "broken".

## Hint: dashboards

Not a rule. Before changing a dashboard, save its prior state (an export to a gitignored place), and build an
unfamiliar card on a scratch view before it goes on a live dashboard; a dashboard that breaks is then one revert away.
