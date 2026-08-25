import type { Tool } from "../types.js";

/**
 * Stub search tool: deterministic, offline, no external dependency. Swap the body of
 * `execute` for a real provider (Brave Search, Tavily, etc.) - the contract (input/output
 * shape, tool name) is what agents and the mock provider are written against, so a real
 * implementation is a drop-in replacement.
 */
export const searchWebTool: Tool<{ query: string }, { results: { title: string; url: string; snippet: string }[] }> = {
  name: "search_web",
  description:
    "Search the web for information relevant to `query`. Returns a short list of results with title, url, and snippet. This boilerplate ships a deterministic stub - replace with a real search API for production use.",
  inputSchema: {
    type: "object",
    required: ["query"],
    properties: { query: { type: "string" } },
  },
  exposable: true,
  async execute(input) {
    return {
      results: [
        {
          title: `Stub result for: ${input.query}`,
          url: "https://example.com/stub-result",
          snippet: `This is a deterministic placeholder result for "${input.query}". Replace tools/builtin/searchWeb with a real search API.`,
        },
      ],
    };
  },
};
