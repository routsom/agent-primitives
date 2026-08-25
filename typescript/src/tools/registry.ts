import type { McpClientManager } from "../mcp/client.js";
import { readArtifactTool } from "./builtin/readArtifact.js";
import { readFileTool } from "./builtin/readFile.js";
import { createMcpCallTool } from "./builtin/mcpCall.js";
import { savePlanTool } from "./builtin/savePlan.js";
import { searchWebTool } from "./builtin/searchWeb.js";
import { spawnSubagentsTool } from "./builtin/spawnSubagents.js";
import { writeArtifactTool } from "./builtin/writeArtifact.js";
import type { Tool } from "./types.js";

export function buildToolRegistry(mcpClient?: McpClientManager): Tool[] {
  const tools: Tool[] = [spawnSubagentsTool, readArtifactTool, writeArtifactTool, savePlanTool, searchWebTool, readFileTool];
  if (mcpClient) tools.push(createMcpCallTool(mcpClient));
  return tools;
}

export * from "./types.js";
