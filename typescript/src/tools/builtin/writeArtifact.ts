import type { Tool } from "../types.js";

export const writeArtifactTool: Tool<{ kind: string; summary: string; content: unknown }, unknown> = {
  name: "write_artifact",
  description:
    "Store a large output (raw findings, a report, code, generated data) in the artifact store and return a lightweight reference. Use this instead of returning large content inline.",
  inputSchema: {
    type: "object",
    required: ["kind", "summary", "content"],
    properties: {
      kind: { type: "string", enum: ["raw-findings", "report", "code", "generated-data", "trace-export"] },
      summary: { type: "string" },
      content: {},
    },
  },
  async execute(input, ctx) {
    return ctx.runtime.writeArtifact({ ...input, createdBy: ctx.agentRole });
  },
};
