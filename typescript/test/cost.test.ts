import { afterEach, describe, expect, it } from "vitest";
import { computeCostUsd, priceKey } from "../src/cost/pricing.js";
import { summarizeCost, formatCostSummary } from "../src/cost/ledger.js";
import { renderDashboard } from "../src/tracing/dashboard.js";
import type { TraceSpan } from "../src/tracing/tracer.js";

describe("cost computation", () => {
  it("prices a known model from the shared table", () => {
    // sonnet: $3/Mtok in, $15/Mtok out. 1000 in + 500 out = 0.003 + 0.0075 = 0.0105.
    const cost = computeCostUsd("anthropic", "claude-sonnet-5", { inputTokens: 1000, outputTokens: 500 });
    expect(cost).toBeCloseTo(0.0105, 6);
  });

  it("applies the cached-input rate to cached tokens", () => {
    // 1000 in of which 800 cached: fresh 200 * 3 + cached 800 * 0.3 + 0 out, per Mtok.
    const cost = computeCostUsd("anthropic", "claude-sonnet-5", { inputTokens: 1000, outputTokens: 0, cachedInputTokens: 800 });
    expect(cost).toBeCloseTo((200 * 3 + 800 * 0.3) / 1_000_000, 9);
  });

  it("costs an unknown model at zero", () => {
    expect(computeCostUsd("acme", "unknown-model", { inputTokens: 1_000_000, outputTokens: 1_000_000 })).toBe(0);
  });

  it("prices mock at zero by default", () => {
    expect(computeCostUsd("mock", "mock-deterministic-1", { inputTokens: 1000, outputTokens: 1000 })).toBe(0);
  });

  it("prices mock at a real model's rate when MOCK_PRICE_AS is set", () => {
    process.env["MOCK_PRICE_AS"] = "anthropic:claude-sonnet-5";
    expect(computeCostUsd("mock", "mock-deterministic-1", { inputTokens: 1000, outputTokens: 0 })).toBeCloseTo(0.003, 6);
  });

  afterEach(() => {
    delete process.env["MOCK_PRICE_AS"];
  });

  it("priceKey joins provider and model", () => {
    expect(priceKey("openai", "gpt-5")).toBe("openai:gpt-5");
  });
});

describe("cost ledger (summarize from spans)", () => {
  const modelCall = (agent: string, model: string, inTok: number, outTok: number, cost: number): TraceSpan => ({
    spanId: `s-${Math.random()}`,
    traceId: "t",
    parentSpanId: null,
    kind: "model_call",
    name: `${agent} turn 0`,
    agentRole: agent,
    delegationDepth: 0,
    startedAt: new Date().toISOString(),
    endedAt: new Date().toISOString(),
    status: "ok",
    tokenUsage: { inputTokens: inTok, outputTokens: outTok },
    costUsd: cost,
    attributes: { model },
  });

  it("totals cost and tokens across only model_call spans, broken down by model and agent", () => {
    const spans: TraceSpan[] = [
      modelCall("lead", "anthropic:claude-opus-4-8", 100, 50, 0.01),
      modelCall("subagent", "anthropic:claude-sonnet-5", 200, 80, 0.004),
      modelCall("subagent", "anthropic:claude-sonnet-5", 300, 20, 0.006),
      // A non-model span carries no spend and must be ignored.
      { ...modelCall("lead", "x", 999, 999, 999), kind: "tool_call" },
    ];
    const summary = summarizeCost(spans);

    expect(summary.total.calls).toBe(3);
    expect(summary.total.inputTokens).toBe(600);
    expect(summary.total.outputTokens).toBe(150);
    expect(summary.total.costUsd).toBeCloseTo(0.02, 6);

    expect(summary.byModel["anthropic:claude-sonnet-5"]?.calls).toBe(2);
    expect(summary.byModel["anthropic:claude-sonnet-5"]?.costUsd).toBeCloseTo(0.01, 6);
    expect(summary.byAgent["subagent"]?.costUsd).toBeCloseTo(0.01, 6);
    expect(summary.byAgent["lead"]?.calls).toBe(1);
  });

  it("renders a readable summary string", () => {
    const summary = summarizeCost([modelCall("lead", "anthropic:claude-opus-4-8", 100, 50, 0.01)]);
    const text = formatCostSummary(summary);
    expect(text).toContain("Run cost:");
    expect(text).toContain("anthropic:claude-opus-4-8");
    expect(text).toContain("lead");
  });
});

describe("dashboard render", () => {
  const span: TraceSpan = {
    spanId: "s1",
    traceId: "trace-abc",
    parentSpanId: null,
    kind: "turn",
    name: "research-task",
    agentRole: null,
    delegationDepth: 0,
    startedAt: new Date().toISOString(),
    endedAt: new Date(Date.now() + 100).toISOString(),
    status: "ok",
  };

  it("injects the payload and leaves no placeholder", () => {
    const html = renderDashboard([span], { runId: "trace-abc", tokenBudget: 250000 });
    expect(html).not.toContain("%%AGENT_PRIMITIVES_PAYLOAD%%");
    expect(html).toContain('"spans"');
    expect(html).toContain("trace-abc");
    expect(html).toContain('"tokenBudget":250000');
  });

  it("escapes < so span data can't break out of the script tag", () => {
    const evil = { ...span, name: "</script><script>alert(1)</script>" };
    const html = renderDashboard([evil], {});
    // The raw closing tag must not appear inside the injected data.
    const dataPart = html.split("ap-payload")[1] ?? "";
    expect(dataPart.slice(0, 2000)).not.toContain("</script><script>alert");
    expect(html).toContain("\\u003c");
  });

  it("embeds eval records for the Evals section", () => {
    const evals = [
      { taskId: "t1", scores: { accuracy: 4, completeness: 4, source_quality: 3, process: 4, disclosure: 5 }, flagForHumanReview: false, structuralFlags: [] },
    ];
    const html = renderDashboard([], { title: "Eval suite" }, evals);
    expect(html).toContain('"evals"');
    expect(html).toContain("t1");
    expect(html).toContain('"source_quality":3');
    expect(html).toContain("Eval suite");
  });
});
