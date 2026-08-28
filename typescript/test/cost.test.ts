import { afterEach, describe, expect, it } from "vitest";
import { computeCostUsd, priceKey } from "../src/cost/pricing.js";
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
});
