import { randomUUID } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { runLeadAgent } from "../src/agents/leadAgent.js";
import { Harness } from "../src/harness/index.js";
import { Orchestrator } from "../src/orchestrator/orchestrator.js";
import { MockChatModel } from "../src/providers/mock.js";
import { buildToolRegistry } from "../src/tools/registry.js";
import { Tracer } from "../src/tracing/tracer.js";

describe("end-to-end orchestrator-worker flow (mock provider)", () => {
  let workDir: string;

  beforeEach(async () => {
    workDir = await mkdtemp(join(tmpdir(), "multiagent-boilerplate-test-"));
  });

  afterEach(async () => {
    await rm(workDir, { recursive: true, force: true });
  });

  it("spawns subagents, writes artifacts, and returns a synthesized final answer", async () => {
    const model = new MockChatModel();
    const harness = new Harness(buildToolRegistry());
    const tracer = new Tracer(() => {});
    const runId = randomUUID();
    const turnSpan = tracer.startSpan("turn", "test-run");

    const orchestrator = new Orchestrator({
      model,
      harness,
      tracer,
      caps: { maxSubagents: 8, maxDelegationDepth: 2, maxToolCallsPerSubagent: 15, maxRunTokens: 0 },
      artifactStoreDir: join(workDir, "artifacts"),
      planMemoryDir: join(workDir, "plans"),
      runId,
      parentSpanId: turnSpan.spanId,
    });

    const result = await runLeadAgent({
      query: "Compare orchestrator-worker and sequential-pipeline topologies.",
      model,
      harness,
      runtime: orchestrator,
      tracer,
      runId,
      parentSpanId: turnSpan.spanId,
    });
    tracer.endSpan(turnSpan, "ok");

    expect(result.status).toBe("ok");
    expect(result.text.length).toBeGreaterThan(0);

    const spans = tracer.allSpans();
    expect(spans.some((s) => s.kind === "agent" && s.agentRole === "lead")).toBe(true);
    expect(spans.some((s) => s.kind === "agent" && s.agentRole === "subagent")).toBe(true);
    expect(spans.some((s) => s.kind === "tool_call" && s.name === "spawn_subagents")).toBe(true);
    expect(spans.some((s) => s.kind === "tool_call" && s.name === "write_artifact")).toBe(true);
  });

  it("rejects a spawn request that exceeds the configured subagent cap", async () => {
    const model = new MockChatModel();
    const harness = new Harness(buildToolRegistry());
    const tracer = new Tracer(() => {});
    const orchestrator = new Orchestrator({
      model,
      harness,
      tracer,
      caps: { maxSubagents: 1, maxDelegationDepth: 2, maxToolCallsPerSubagent: 15, maxRunTokens: 0 },
      artifactStoreDir: join(workDir, "artifacts"),
      planMemoryDir: join(workDir, "plans"),
      runId: randomUUID(),
    });

    const task = {
      taskId: "a",
      role: "subagent",
      objective: "x",
      outputFormat: "y",
      allowedTools: ["search_web"],
      boundaries: "z",
      budget: { maxToolCalls: 5 },
    };

    await expect(orchestrator.spawnSubagents([task, task], 1)).rejects.toThrow();
  });
});
