import type { Tool } from "../types.js";

export const spawnSubagentsTool: Tool<{ tasks: unknown[] }, unknown> = {
  name: "spawn_subagents",
  description:
    "Spawn one or more subagents in parallel, each with its own isolated context, given an explicit AgentTask (objective, output format, allowed tools, boundaries, budget) per specs/schemas/agent-task.schema.json. Returns each subagent's distilled findings plus an artifact reference. Subject to the harness's subagent-count and delegation-depth caps.",
  inputSchema: {
    type: "object",
    required: ["tasks"],
    properties: {
      tasks: { type: "array", items: { type: "object" } },
    },
  },
  async execute(input, ctx) {
    return ctx.runtime.spawnSubagents(input.tasks, ctx.delegationDepth + 1);
  },
};
