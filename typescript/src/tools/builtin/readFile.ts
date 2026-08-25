import { readFile } from "node:fs/promises";
import { resolve, isAbsolute } from "node:path";
import type { Tool } from "../types.js";

const workspaceRoot = process.cwd();

/** Reads a file scoped to the current working directory - agents cannot read outside it. */
export const readFileTool: Tool<{ path: string }, { content: string }> = {
  name: "read_file",
  description: "Read a UTF-8 text file by path, relative to the project working directory.",
  inputSchema: {
    type: "object",
    required: ["path"],
    properties: { path: { type: "string" } },
  },
  async execute(input) {
    const target = isAbsolute(input.path) ? input.path : resolve(workspaceRoot, input.path);
    if (!target.startsWith(workspaceRoot)) {
      throw new Error(`read_file: path escapes workspace root: ${input.path}`);
    }
    const content = await readFile(target, "utf-8");
    return { content };
  },
};
