import { describe, expect, it } from "vitest";
import { Harness, redact, type AuditEntry, type AuditSink } from "../src/harness/index.js";
import { buildToolRegistry } from "../src/tools/registry.js";

class CapturingSink implements AuditSink {
  entries: AuditEntry[] = [];
  record(entry: AuditEntry): void {
    this.entries.push(entry);
  }
}

const subagentRole = {
  role: "subagent",
  allowedTools: ["search_web"],
  canSpawn: [],
  maxDelegationDepth: 0,
  budget: { maxToolCalls: 5 },
};

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

describe("redaction", () => {
  it("redacts sensitive keys at any depth, leaves others intact", () => {
    const out = redact({ query: "hello", apiKey: "sk-123", nested: { password: "p", city: "NYC" }, list: [{ token: "t" }] });
    expect(out).toEqual({ query: "hello", apiKey: "[redacted]", nested: { password: "[redacted]", city: "NYC" }, list: [{ token: "[redacted]" }] });
  });
});

describe("harness audit (100% coverage)", () => {
  it("records an audit entry for a successful call, with correlation ids and redacted params", async () => {
    const sink = new CapturingSink();
    const harness = new Harness(buildToolRegistry(), { auditSink: sink });
    const outcome = await harness.execute(
      subagentRole,
      { idempotencyKey: "k1", toolName: "search_web", input: { query: "x", apiKey: "sk-secret" }, delegationDepth: 1, correlation: { traceId: "tr", sessionId: "se", requestId: "rq" } },
      noRuntime,
    );
    expect(outcome.status).toBe("ok");
    expect(sink.entries).toHaveLength(1);
    const entry = sink.entries[0]!;
    expect(entry).toMatchObject({ toolName: "search_web", agentRole: "subagent", resultStatus: "ok", traceId: "tr", sessionId: "se", requestId: "rq" });
    expect(entry.paramsRedacted).toEqual({ query: "x", apiKey: "[redacted]" });
  });

  it("records an entry even when the harness REJECTS the call (a scope violation)", async () => {
    const sink = new CapturingSink();
    const harness = new Harness(buildToolRegistry(), { auditSink: sink });
    const outcome = await harness.execute(
      subagentRole,
      { idempotencyKey: "k2", toolName: "spawn_subagents", input: {}, delegationDepth: 0 },
      noRuntime,
    );
    expect(outcome.status).toBe("rejected");
    expect(sink.entries).toHaveLength(1);
    expect(sink.entries[0]).toMatchObject({ toolName: "spawn_subagents", resultStatus: "rejected", errorType: "auth" });
  });
});
