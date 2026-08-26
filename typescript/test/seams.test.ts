import { describe, expect, it } from "vitest";
import { Harness, ToolCircuitBreaker } from "../src/harness/index.js";
import { toOtlpSpan } from "../src/tracing/otlp.js";
import { Tracer } from "../src/tracing/tracer.js";
import type { Tool } from "../src/tools/types.js";

const noRuntime = {
  async spawnSubagents(): Promise<never> {
    throw new Error("n/a");
  },
  async writeArtifact() {
    return {};
  },
  async readArtifact() {
    return {};
  },
  async savePlan() {},
};

const role = { role: "subagent", allowedTools: ["flaky", "echo"], canSpawn: [], maxDelegationDepth: 0, budget: { maxToolCalls: 100 } };

describe("tool circuit breaker", () => {
  it("opens after the failure threshold and short-circuits further calls", () => {
    const breaker = new ToolCircuitBreaker({ failureThreshold: 3, windowMs: 1000, cooldownMs: 1000 });
    expect(breaker.isOpen("t")).toBe(false);
    breaker.recordFailure("t");
    breaker.recordFailure("t");
    expect(breaker.isOpen("t")).toBe(false);
    breaker.recordFailure("t");
    expect(breaker.isOpen("t")).toBe(true);
  });

  it("half-opens after cooldown", () => {
    const breaker = new ToolCircuitBreaker({ failureThreshold: 1, windowMs: 1000, cooldownMs: 500 });
    breaker.recordFailure("t", 0);
    expect(breaker.isOpen("t", 100)).toBe(true);
    expect(breaker.isOpen("t", 600)).toBe(false); // cooldown elapsed
  });

  it("a success resets the failure count", () => {
    const breaker = new ToolCircuitBreaker({ failureThreshold: 2, windowMs: 1000, cooldownMs: 1000 });
    breaker.recordFailure("t");
    breaker.recordSuccess("t");
    breaker.recordFailure("t");
    expect(breaker.isOpen("t")).toBe(false);
  });

  it("harness short-circuits a tool whose circuit is open", async () => {
    const flaky: Tool = {
      name: "flaky",
      description: "always throws",
      inputSchema: { type: "object" },
      async execute() {
        throw new Error("503 backend down");
      },
    };
    const harness = new Harness([flaky], { circuitBreaker: { failureThreshold: 2, windowMs: 10_000, cooldownMs: 10_000 } });
    await harness.execute(role, { idempotencyKey: "a", toolName: "flaky", input: {}, delegationDepth: 0 }, noRuntime);
    await harness.execute(role, { idempotencyKey: "b", toolName: "flaky", input: {}, delegationDepth: 0 }, noRuntime);
    // Breaker is now open: the next call is rejected without invoking the tool.
    const outcome = await harness.execute(role, { idempotencyKey: "c", toolName: "flaky", input: {}, delegationDepth: 0 }, noRuntime);
    expect(outcome.status).toBe("rejected");
    if (outcome.status !== "ok") expect(outcome.error.message).toContain("circuit is open");
  });
});

describe("boundary guardrail (sanitize seam)", () => {
  it("applies the sanitizer to tool output before it returns to the model", async () => {
    const echo: Tool = {
      name: "echo",
      description: "echoes input",
      inputSchema: { type: "object" },
      async execute(input) {
        return input;
      },
    };
    const harness = new Harness([echo], {
      sanitize: (_boundary, content) => ({ sanitized: true, original: content }),
    });
    const outcome = await harness.execute(role, { idempotencyKey: "x", toolName: "echo", input: { hi: 1 }, delegationDepth: 0 }, noRuntime);
    expect(outcome.status).toBe("ok");
    if (outcome.status === "ok") expect(outcome.output).toEqual({ sanitized: true, original: { hi: 1 } });
  });
});

describe("OTLP span mapping", () => {
  it("maps a TraceSpan to the OTLP/JSON shape", () => {
    const tracer = new Tracer(() => {});
    const span = tracer.startSpan("model_call", "lead turn 0", { agentRole: "lead", delegationDepth: 0 });
    tracer.endSpan(span, "ok", { tokenUsage: { inputTokens: 10, outputTokens: 5 } });
    const otlp = toOtlpSpan(span);
    expect(otlp).toMatchObject({ name: "lead turn 0", spanId: span.spanId, traceId: span.traceId });
    expect(otlp.status).toEqual({ code: 1 });
    expect(Array.isArray(otlp.attributes)).toBe(true);
  });
});
