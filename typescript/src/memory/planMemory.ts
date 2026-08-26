import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

/**
 * The seam for durable plan storage. `PlanMemory` (local filesystem) is the shipped default;
 * a production durable-job store would implement this same interface against a database, but
 * the save/load-by-runId contract stays the same (notes section 5). See docs/extending.md.
 */
export interface PlanStore {
  save(runId: string, plan: unknown): Promise<void>;
  load(runId: string): Promise<unknown | undefined>;
}

/** Local filesystem plan store (default). */
export class PlanMemory implements PlanStore {
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
