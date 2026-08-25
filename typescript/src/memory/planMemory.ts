import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

/**
 * Persists the lead agent's plan before subagents are spawned, so a context truncation
 * mid-run doesn't lose the strategy (notes section 5). One plan file per run, keyed by
 * runId - a durable job store in production would back this with a database instead of the
 * filesystem, but the interface (save/load by runId) stays the same.
 */
export class PlanMemory {
  constructor(private readonly rootDir: string) {}

  async save(runId: string, plan: unknown): Promise<void> {
    await mkdir(this.rootDir, { recursive: true });
    const path = resolve(this.rootDir, `${runId}.plan.json`);
    await writeFile(path, JSON.stringify({ savedAt: new Date().toISOString(), plan }, null, 2), "utf-8");
  }

  async load(runId: string): Promise<unknown | undefined> {
    const path = resolve(this.rootDir, `${runId}.plan.json`);
    try {
      const raw = await readFile(path, "utf-8");
      return (JSON.parse(raw) as { plan: unknown }).plan;
    } catch {
      return undefined;
    }
  }
}
