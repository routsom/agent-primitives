import type { Tool, ToolRuntime } from "../tools/types.js";
import { IdempotencyCache } from "./idempotency.js";
import type { AgentRoleDef } from "./scope.js";
import { assertToolAllowed } from "./scope.js";

export * from "./scope.js";
export * from "./budget.js";
export * from "./idempotency.js";
export * from "./validate.js";
export * from "./schemas.js";

export interface HarnessToolCall {
  idempotencyKey: string;
  toolName: string;
  input: Record<string, unknown>;
  delegationDepth: number;
}

/**
 * Shared infrastructure every agent's tool call routes through - no agent-to-agent shortcut
 * around it (notes section 7). Validates scope, applies idempotency, and executes.
 */
export class Harness {
  private readonly tools = new Map<string, Tool>();
  private readonly idempotency = new IdempotencyCache();

  constructor(tools: Tool[]) {
    for (const tool of tools) this.tools.set(tool.name, tool);
  }

  async execute(role: AgentRoleDef, call: HarnessToolCall, runtime: ToolRuntime): Promise<unknown> {
    assertToolAllowed(role, call.toolName);
    const tool = this.tools.get(call.toolName);
    if (!tool) throw new Error(`harness: unknown tool "${call.toolName}"`);

    return this.idempotency.run(call.idempotencyKey, () =>
      tool.execute(call.input, {
        agentRole: role.role,
        delegationDepth: call.delegationDepth,
        runtime,
      }),
    );
  }

  toolDefinitions(role: AgentRoleDef): { name: string; description: string; inputSchema: Record<string, unknown> }[] {
    return role.allowedTools
      .map((name) => this.tools.get(name))
      .filter((tool): tool is Tool => Boolean(tool))
      .map((tool) => ({ name: tool.name, description: tool.description, inputSchema: tool.inputSchema }));
  }
}
