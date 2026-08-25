import type { McpClientManager } from "../../mcp/client.js";
import type { Tool } from "../types.js";

export function createMcpCallTool(manager: McpClientManager): Tool<{ server: string; tool: string; input: Record<string, unknown> }, unknown> {
  return {
    name: "mcp_call",
    description: "Call a tool exposed by a connected external MCP server (config/mcp-servers.json), by server name and tool name.",
    inputSchema: {
      type: "object",
      required: ["server", "tool", "input"],
      properties: {
        server: { type: "string" },
        tool: { type: "string" },
        input: { type: "object" },
      },
    },
    async execute(input) {
      return manager.callTool(input.server, input.tool, input.input);
    },
  };
}
