import { describe, expect, it } from "vitest";
import { assertToolAllowed, assertDepthWithinCap, assertSubagentCountWithinCap, HarnessScopeError, DelegationDepthExceededError, SubagentCountExceededError, ToolCallBudget, ToolCallBudgetExceededError, IdempotencyCache } from "../src/harness/index.js";

describe("harness scope", () => {
  it("allows a tool explicitly granted to the role", () => {
    const role = { role: "subagent", allowedTools: ["search_web"], canSpawn: [], maxDelegationDepth: 0, budget: { maxToolCalls: 5 } };
    expect(() => assertToolAllowed(role, "search_web")).not.toThrow();
  });

  it("rejects a tool not granted to the role", () => {
    const role = { role: "subagent", allowedTools: ["search_web"], canSpawn: [], maxDelegationDepth: 0, budget: { maxToolCalls: 5 } };
    expect(() => assertToolAllowed(role, "spawn_subagents")).toThrow(HarnessScopeError);
  });
});

describe("harness budget caps", () => {
  it("rejects delegation depth beyond the cap", () => {
    expect(() => assertDepthWithinCap(3, 2)).toThrow(DelegationDepthExceededError);
    expect(() => assertDepthWithinCap(2, 2)).not.toThrow();
  });

  it("rejects a subagent count beyond the cap", () => {
    expect(() => assertSubagentCountWithinCap(9, 8)).toThrow(SubagentCountExceededError);
    expect(() => assertSubagentCountWithinCap(8, 8)).not.toThrow();
  });

  it("enforces a per-role tool-call budget", () => {
    const budget = new ToolCallBudget("subagent", 2);
    budget.consume();
    budget.consume();
    expect(() => budget.consume()).toThrow(ToolCallBudgetExceededError);
  });
});

describe("idempotency cache", () => {
  it("runs a given key's function only once for concurrent calls", async () => {
    let calls = 0;
    const cache = new IdempotencyCache();
    const fn = async () => {
      calls++;
      return "result";
    };
    const [a, b] = await Promise.all([cache.run("key-1", fn), cache.run("key-1", fn)]);
    expect(a).toBe("result");
    expect(b).toBe("result");
    expect(calls).toBe(1);
  });
});
