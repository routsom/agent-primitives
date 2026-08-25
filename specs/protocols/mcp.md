# MCP integration contract

Both runtimes implement the same two roles against the Model Context Protocol.

## MCP client (`mcp/client`)

Mounts external MCP servers' tools into this system's tool registry so any agent role can be
granted them like a native tool.

- Config lives in `config/mcp-servers.json` (per runtime) — list of `{name, transport,
  command|url, env}`. See `config/mcp-servers.example.json` for the format.
- Every tool an MCP server exposes is wrapped in the local `ToolCallEnvelope` /
  `ToolResultEnvelope` (`specs/schemas/tool-envelope.schema.json`) before it reaches an agent
  — the harness's validation, idempotency, and per-role scoping apply to MCP tools exactly
  like local ones. An MCP server is an external, untrusted boundary (notes §7); nothing about
  going through MCP exempts a tool call from harness checks.
- Tool descriptions returned by an external MCP server are treated as first-class
  documentation the way local tool descriptions are (notes §6) — if an external server's tool
  description is ambiguous, wrap it locally with a clarified description rather than passing
  it through unedited.

## MCP server (`mcp/server`)

Exposes this system's own tools (and optionally whole agent roles as callable operations) as
an MCP server, so other MCP-compatible clients (including other instances of this boilerplate)
can use them.

- Only tools explicitly marked `exposable: true` in their definition are surfaced externally
  — internal-only tools (e.g. `save_plan`, direct artifact-store writes) are never exposed by
  default.
- Requests arriving over the MCP server are subject to the same harness auth/scope checks as
  any other caller. "It came in over MCP" is not a trust boundary shortcut.

## Where this is implemented

- TypeScript: `typescript/src/mcp/` using `@modelcontextprotocol/sdk`.
- Python: `python/src/mcp_/` using the official `mcp` package.
