import { randomUUID } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { runLeadAgent } from "../src/agents/leadAgent.js";
import { Harness } from "../src/harness/index.js";
import { Orchestrator } from "../src/orchestrator/orchestrator.js";
import { CheckpointMemory } from "../src/orchestrator/checkpoint.js";
import { MockChatModel } from "../src/providers/mock.js";
import type { ChatModel } from "../src/providers/types.js";
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

describe("durable execution (resume from checkpoint)", () => {
  let workDir: string;
  const caps = { maxSubagents: 8, maxDelegationDepth: 2, maxToolCallsPerSubagent: 15, maxRunTokens: 0 };
  const task = {
    taskId: "sub-1",
    role: "subagent",
    objective: "Investigate angle A of the topic",
    outputFormat: "bullet list",
    allowedTools: ["search_web", "write_artifact"],
    boundaries: "Angle A only.",
    budget: { maxToolCalls: 15, maxDelegationDepth: 0 },
  };

  // A model that fails on every call - stands in for "the subagent would re-run and cost tokens".
  const throwingModel: ChatModel = {
    provider: "mock",
    model: "throws",
    async complete() {
      throw new Error("model must not be called when a checkpoint exists");
    },
  };

  beforeEach(async () => {
    workDir = await mkdtemp(join(tmpdir(), "multiagent-boilerplate-ckpt-"));
  });
  afterEach(async () => {
    await rm(workDir, { recursive: true, force: true });
  });

  function orchestratorFor(model: ChatModel, runId: string, tracer: Tracer): Orchestrator {
    return new Orchestrator({
      model,
      harness: new Harness(buildToolRegistry()),
      tracer,
      caps,
      artifactStoreDir: join(workDir, "artifacts"),
      planMemoryDir: join(workDir, "plans"),
      checkpointDir: join(workDir, "checkpoints"),
      runId,
    });
  }

  it("restores a completed subagent on resume instead of re-running it", async () => {
    const runId = randomUUID();

    // First run: succeeds and writes a checkpoint.
    const first = await orchestratorFor(new MockChatModel(), runId, new Tracer(() => {})).spawnSubagents([task], 1);
    expect(first.results[0]?.status).toBe("ok");
    expect(await new CheckpointMemory(join(workDir, "checkpoints")).load(runId, "sub-1")).toBeDefined();

    // Resume with a model that throws: if the subagent re-ran, this would error. Restore avoids it.
    const tracer = new Tracer(() => {});
    const second = await orchestratorFor(throwingModel, runId, tracer).spawnSubagents([task], 1);
    expect(second.partial).toBe(false);
    expect(second.results[0]?.status).toBe("ok");
    expect(second.results[0]?.text).toBe(first.results[0]?.text);
    expect(tracer.allSpans().some((s) => s.attributes?.["restoredFromCheckpoint"] === true)).toBe(true);
  });

  it("does not checkpoint a failed subagent, so it re-runs on resume", async () => {
    const runId = randomUUID();
    // First run fails outright - nothing should be checkpointed.
    const failed = await orchestratorFor(throwingModel, runId, new Tracer(() => {})).spawnSubagents([task], 1);
    expect(failed.results[0]?.status).toBe("error");
    expect(await new CheckpointMemory(join(workDir, "checkpoints")).load(runId, "sub-1")).toBeUndefined();

    // Resume with a working model: because nothing was checkpointed, it actually runs and succeeds.
    const recovered = await orchestratorFor(new MockChatModel(), runId, new Tracer(() => {})).spawnSubagents([task], 1);
    expect(recovered.results[0]?.status).toBe("ok");
  });
});
