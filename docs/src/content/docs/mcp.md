---
title: MCP
description: Mounting external MCP servers as tools, and exposing this system's own tools over MCP.
---

Both runtimes implement two roles against the Model Context Protocol, per
`specs/protocols/mcp.md`.

## MCP client

Mounts external MCP servers' tools into the local tool registry so any agent role can be
granted them like a native tool.

- Configure servers in `config/mcp-servers.json` (TypeScript) or
  `config/mcp_servers.json` (Python) - a list of `{name, command, args, env}`.
- Every tool an MCP server exposes is wrapped in the same tool contract
  (`specs/schemas/tool-envelope.schema.json`) local tools use before it reaches an agent - the
  [harness's](/harness/) validation, idempotency, and per-role scoping apply to MCP tools
  exactly like local ones. An MCP server is an external, untrusted boundary; nothing about going
  through MCP exempts a tool call from harness checks.
- If an external server's tool description is ambiguous, wrap it locally with a clarified
  description rather than passing it through unedited - tool descriptions are a first-class
  engineering artifact (`reference/multi-agent-architecture-notes.md` section 6).

```ts
// typescript/src/mcp/client.ts
const manager = new McpClientManager();
await manager.connect([{ name: "filesystem", command: "npx", args: ["-y", "@modelcontextprotocol/server-filesystem", "."] }]);
```

```py
# python/src/multiagent_boilerplate/mcp_/client.py
manager = McpClientManager()
await manager.connect([McpServerConfig(name="filesystem", command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "."])])
```

## MCP server

Exposes this system's own tools as an MCP server, so other MCP-compatible clients - including
another instance of this boilerplate - can call them.

- Only tools explicitly marked `exposable: true` (TypeScript) / `exposable = True` (Python) are
  surfaced externally. Internal-only tools (`spawn_subagents`, `save_plan`, direct artifact-store
  writes) are never exposed by default.
- Requests arriving over the MCP server are subject to the same harness auth/scope checks as any
  other caller.

```bash
# TypeScript
npx tsx -e "import { startMcpServer } from './src/mcp/server.js'; import { buildToolRegistry } from './src/tools/registry.js'; startMcpServer(buildToolRegistry());"
```

```bash
# Python
uv run python -c "from multiagent_boilerplate.mcp_.server import run_mcp_server; from multiagent_boilerplate.tools.registry import build_tool_registry; run_mcp_server(build_tool_registry())"
```

Both use the official SDKs directly (`@modelcontextprotocol/sdk`, `mcp`) - no framework wrapper
in between.
