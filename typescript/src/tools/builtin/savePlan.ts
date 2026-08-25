import type { Tool } from "../types.js";

export const savePlanTool: Tool<{ plan: unknown }, { saved: true }> = {
  name: "save_plan",
  description:
    "Persist the current plan to durable memory before spawning subagents, so a context truncation mid-run doesn't lose the strategy.",
  inputSchema: {
    type: "object",
    required: ["plan"],
    properties: { plan: {} },
  },
  async execute(input, ctx) {
    await ctx.runtime.savePlan(input.plan);
    return { saved: true };
  },
};
