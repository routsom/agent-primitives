import type { Tool } from "../types.js";

export const readArtifactTool: Tool<{ artifactId: string }, unknown> = {
  name: "read_artifact",
  description: "Fetch the full content of a previously stored artifact by id, when a distilled summary isn't enough.",
  inputSchema: {
    type: "object",
    required: ["artifactId"],
    properties: { artifactId: { type: "string" } },
  },
  async execute(input, ctx) {
    return ctx.runtime.readArtifact(input.artifactId);
  },
};
