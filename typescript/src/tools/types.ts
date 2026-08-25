export interface ToolContext {
  agentRole: string;
  delegationDepth: number;
  /** Present when the tool needs to recurse into the agent runtime (e.g. spawn_subagents). */
  runtime: ToolRuntime;
}

/** Narrow surface tools need back into the runtime, avoiding a circular full-runtime import. */
export interface ToolRuntime {
  spawnSubagents(tasks: unknown[], depth: number): Promise<unknown>;
  writeArtifact(input: { kind: string; summary: string; content: unknown; createdBy: string }): Promise<unknown>;
  readArtifact(artifactId: string): Promise<unknown>;
  savePlan(plan: unknown): Promise<void>;
}

export interface Tool<Input = unknown, Output = unknown> {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  /** Exposed to external MCP clients when true (specs/protocols/mcp.md). Internal-only tools default to false. */
  exposable?: boolean;
  execute(input: Input, ctx: ToolContext): Promise<Output>;
}
