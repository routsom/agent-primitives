import { describe, expect, it } from "vitest";
import { deriveReviewFlags } from "../src/agents/review.js";
import type { ToolError } from "../src/harness/index.js";

const transient: ToolError = { type: "transient", message: "x", retryable: true };
const auth: ToolError = { type: "auth", message: "x", retryable: false };

describe("deriveReviewFlags (deterministic, no LLM)", () => {
  it("flags a clean, substantive ok run as not needing review", () => {
    const flags = deriveReviewFlags({ status: "ok", unrecoveredErrors: [], finalText: "A perfectly reasonable, sufficiently long answer.", lastStopReason: "end_turn" });
    expect(flags).toEqual([]);
  });

  it("flags partial completion", () => {
    expect(deriveReviewFlags({ status: "partial", unrecoveredErrors: [], finalText: "stopped" })).toContain("partial_completion");
  });

  it("flags each distinct unrecovered tool error type once", () => {
    const flags = deriveReviewFlags({ status: "ok", unrecoveredErrors: [transient, transient, auth], finalText: "a sufficiently long final answer here" });
    expect(flags).toContain("unrecovered_tool_error:transient");
    expect(flags).toContain("unrecovered_tool_error:auth");
    expect(flags.filter((f) => f === "unrecovered_tool_error:transient")).toHaveLength(1);
  });

  it("flags max_tokens truncation", () => {
    expect(deriveReviewFlags({ status: "ok", unrecoveredErrors: [], finalText: "a sufficiently long final answer here", lastStopReason: "max_tokens" })).toContain("max_tokens_truncation");
  });

  it("flags a suspiciously empty ok response", () => {
    expect(deriveReviewFlags({ status: "ok", unrecoveredErrors: [], finalText: "  ok  ", lastStopReason: "end_turn" })).toContain("empty_response");
  });
});
