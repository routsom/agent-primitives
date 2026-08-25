import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import type { Tool } from "../tools/types.js";

/**
 * Exposes this system's own exposable tools (specs/protocols/mcp.md) as an MCP server, so
 * other MCP-compatible clients - including another instance of this boilerplate - can call
 * them. Only tools with `exposable: true` are surfaced.
 */
export function createMcpServer(tools: Tool[]): McpServer {
  const server = new McpServer({ name: "agent-primitives", version: "0.1.0" });

  for (const tool of tools) {
    if (!tool.exposable) continue;
    server.tool(tool.name, tool.description, jsonSchemaToZodShape(tool.inputSchema), async (input: Record<string, unknown>) => {
      const output = await tool.execute(input, {
        agentRole: "mcp-external",
        delegationDepth: 0,
        runtime: {
          spawnSubagents: () => {
            throw new Error("spawn_subagents is not exposed over MCP");
          },
          writeArtifact: () => {
            throw new Error("write_artifact is not exposed over MCP");
          },
          readArtifact: () => {
            throw new Error("read_artifact is not exposed over MCP");
          },
          savePlan: () => {
            throw new Error("save_plan is not exposed over MCP");
          },
        },
      });
      return { content: [{ type: "text", text: JSON.stringify(output) }] };
    });
  }

  return server;
}

export async function startMcpServer(tools: Tool[]): Promise<void> {
  const server = createMcpServer(tools);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

/** Minimal JSON-Schema-object -> zod-shape conversion, sufficient for this boilerplate's flat tool inputs. */
function jsonSchemaToZodShape(schema: Record<string, unknown>): Record<string, z.ZodTypeAny> {
  const properties = (schema["properties"] as Record<string, { type?: string }>) ?? {};
  const required = new Set((schema["required"] as string[]) ?? []);
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const [key, prop] of Object.entries(properties)) {
    let field: z.ZodTypeAny;
    switch (prop.type) {
      case "string":
        field = z.string();
        break;
      case "number":
        field = z.number();
        break;
      case "boolean":
        field = z.boolean();
        break;
      case "array":
        field = z.array(z.unknown());
        break;
      default:
        field = z.unknown();
    }
    shape[key] = required.has(key) ? field : field.optional();
  }
  return shape;
}
