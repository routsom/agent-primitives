import { runSubagent } from "../agents/subagent.js";
import type { AgentResult, AgentTask } from "../agents/types.js";
import { LocalArtifactStore, type ArtifactRef, type WriteArtifactInput } from "../artifacts/store.js";
import type { HarnessCaps } from "../config/index.js";
import { assertDepthWithinCap, assertSubagentCountWithinCap, validateAgentTask } from "../harness/index.js";
import type { Harness } from "../harness/index.js";
import { PlanMemory } from "../memory/planMemory.js";
import type { ChatModel } from "../providers/types.js";
import type { ToolRuntime } from "../tools/types.js";
import type { Tracer } from "../tracing/tracer.js";

export interface OrchestratorOptions {
  model: ChatModel;
  harness: Harness;
  tracer: Tracer;
  caps: HarnessCaps;
  artifactStoreDir: string;
  planMemoryDir: string;
  runId: string;
  parentSpanId?: string | null;
  /** How many times to retry a subagent whose run throws unexpectedly (not tool-level failures, which the model handles itself). */
  subagentRetries?: number;
}

export interface SpawnSubagentsResult {
  results: AgentResult[];
  partial: boolean;
}

/**
 * Implements ToolRuntime.spawnSubagents: parallel fan-out/fan-in with the two circuit
 * breakers from the notes (delegation-depth cap, per-subagent retry cap) and an explicit
 * partial-completion policy - proceed with what succeeded, flag the gap, never silently
 * present partial results as complete (notes section 9, diagrams section 3).
 */
export class Orchestrator implements ToolRuntime {
  private readonly artifactStore: LocalArtifactStore;
  private readonly planMemory: PlanMemory;
  private readonly subagentRetries: number;

  constructor(private readonly opts: OrchestratorOptions) {
    this.artifactStore = new LocalArtifactStore(opts.artifactStoreDir);
    this.planMemory = new PlanMemory(opts.planMemoryDir);
    this.subagentRetries = opts.subagentRetries ?? 2;
  }

  async spawnSubagents(rawTasks: unknown[], depth: number): Promise<SpawnSubagentsResult> {
    assertSubagentCountWithinCap(rawTasks.length, this.opts.caps.maxSubagents);
    assertDepthWithinCap(depth, this.opts.caps.maxDelegationDepth);

    const tasks = rawTasks.map((raw) => {
      validateAgentTask(raw);
      return raw as AgentTask;
    });

    const results = await Promise.all(tasks.map((task) => this.runWithRetry(task, depth)));
    const partial = results.some((r) => r.status !== "ok");
    return { results, partial };
  }

  async writeArtifact(input: WriteArtifactInput): Promise<ArtifactRef> {
    return this.artifactStore.write(input);
  }

  async readArtifact(artifactId: string): Promise<unknown> {
    return this.artifactStore.read(artifactId);
  }

  async savePlan(plan: unknown): Promise<void> {
    return this.planMemory.save(this.opts.runId, plan);
  }

  async loadPlan(): Promise<unknown | undefined> {
    return this.planMemory.load(this.opts.runId);
  }

  private async runWithRetry(task: AgentTask, depth: number, attemptsLeft = this.subagentRetries): Promise<AgentResult> {
    try {
      return await runSubagent({
        task,
        model: this.opts.model,
        harness: this.opts.harness,
        runtime: this,
        tracer: this.opts.tracer,
        parentSpanId: this.opts.parentSpanId ?? null,
        delegationDepth: depth,
      });
    } catch (error) {
      if (attemptsLeft > 1) return this.runWithRetry(task, depth, attemptsLeft - 1);
      return { taskId: task.taskId, role: task.role, text: `subagent failed after retries: ${String(error)}`, artifactRefs: [], status: "error" };
    }
  }
}
