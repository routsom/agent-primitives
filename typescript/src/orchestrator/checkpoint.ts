import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { AgentResult } from "../agents/types.js";

/**
 * The seam for durable, resumable execution (notes section 12). The expensive unit of work in
 * an orchestrator-worker run is a subagent; when a swarm dies partway through fan-out, resuming
 * should skip the subagents that already finished and re-run only the missing ones. A checkpoint
 * is one such completed unit, keyed by (runId, taskId).
 *
 * `CheckpointMemory` (local filesystem) is the shipped default; a production durable-job store
 * (a database, a workflow engine like Temporal) implements this same save/load-by-key contract.
 * Mirrors specs/schemas/run-checkpoint.schema.json. See docs/extending.md.
 */
export interface CheckpointStore {
  /** Persist a completed subagent result. Only 'ok' results are ever passed here (see policy in the orchestrator). */
  save(runId: string, taskId: string, result: AgentResult): Promise<void>;
  /** Return a previously-checkpointed result for this task, or undefined if none exists (fresh work). */
  load(runId: string, taskId: string): Promise<AgentResult | undefined>;
}

/** Local filesystem checkpoint store (default). One file per (runId, taskId). */
export class CheckpointMemory implements CheckpointStore {
  constructor(private readonly rootDir: string) {}

  private path(runId: string, taskId: string): string {
    // taskId is validated against the agent-task schema before it reaches here; encode anyway so
    // an unusual id can never escape the checkpoint directory.
    return resolve(this.rootDir, `${runId}.${encodeURIComponent(taskId)}.checkpoint.json`);
  }

  async save(runId: string, taskId: string, result: AgentResult): Promise<void> {
    await mkdir(this.rootDir, { recursive: true });
    const record = { runId, taskId, savedAt: new Date().toISOString(), result };
    await writeFile(this.path(runId, taskId), JSON.stringify(record, null, 2), "utf-8");
  }

  async load(runId: string, taskId: string): Promise<AgentResult | undefined> {
    try {
      const raw = await readFile(this.path(runId, taskId), "utf-8");
      return (JSON.parse(raw) as { result: AgentResult }).result;
    } catch {
      return undefined;
    }
  }
}
