import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

export interface McpServerConfig {
  name: string;
  command: string;
  args?: string[];
  env?: Record<string, string>;
}

/**
 * Mounts external MCP servers so their tools can be called through this system's own tool
 * contract. See specs/protocols/mcp.md - every call still passes through the harness like a
 * local tool call; MCP is a source of tools, not a trust boundary bypass.
 */
export class McpClientManager {
  private readonly clients = new Map<string, Client>();

  async connect(servers: McpServerConfig[]): Promise<void> {
    for (const server of servers) {
      const transport = new StdioClientTransport({
        command: server.command,
        args: server.args ?? [],
        env: server.env,
      });
      const client = new Client({ name: "agent-primitives", version: "0.1.0" }, { capabilities: {} });
      await client.connect(transport);
      this.clients.set(server.name, client);
    }
  }

  async listTools(serverName: string) {
    const client = this.require(serverName);
    return client.listTools();
  }

  async callTool(serverName: string, toolName: string, input: Record<string, unknown>) {
    const client = this.require(serverName);
    return client.callTool({ name: toolName, arguments: input });
  }

  async closeAll(): Promise<void> {
    await Promise.all([...this.clients.values()].map((c) => c.close()));
    this.clients.clear();
  }

  private require(serverName: string): Client {
    const client = this.clients.get(serverName);
    if (!client) throw new Error(`mcp: server "${serverName}" is not connected - check config/mcp-servers.json`);
    return client;
  }
}
