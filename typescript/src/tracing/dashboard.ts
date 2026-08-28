import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { platform } from "node:os";
import { dirname, resolve } from "node:path";
import { repoRootPath } from "../harness/schemas.js";
import type { TraceSpan } from "./tracer.js";

/**
 * Writes a self-contained, zero-dependency profiler dashboard for a run by injecting its trace
 * spans into the shared dashboard/template.html. Both runtimes read the same template, so the
 * dashboard can't drift between TypeScript and Python. No server, no build step - open the file.
 */
export interface DashboardMeta {
  runId?: string;
  title?: string;
  tokenBudget?: number;
  costBudget?: number;
  live?: boolean;
}

/**
 * One LLM-judge verdict for a task (evals/), linked to its run by taskId. Rendered in the
 * dashboard's Evals section as a per-criterion heatmap + averaged radar. `structuralFlags` are
 * the deterministic review flags the run itself produced (notes section 16a).
 */
export interface EvalRecord {
  taskId: string;
  scores: Record<string, number>;
  flagForHumanReview: boolean;
  structuralFlags: string[];
}

export const PAYLOAD_SENTINEL = "%%AGENT_PRIMITIVES_PAYLOAD%%";

/** Reads the shared dashboard template (both runtimes use the same file, so it can't drift). */
export function readTemplate(): string {
  return readFileSync(resolve(repoRootPath, "dashboard", "template.html"), "utf-8");
}

/** Builds the full dashboard HTML by injecting the run payload at the single sentinel. */
export function renderDashboard(spans: readonly TraceSpan[], meta: DashboardMeta = {}, evals: readonly EvalRecord[] = []): string {
  // Embed as JSON in a <script type="application/json"> tag; escape `<` so a stray "</script>"
  // in span data can never break out of the tag.
  const json = JSON.stringify({ meta, spans, evals }).replace(/</g, "\\u003c");
  // Use a function replacement so `$` sequences in the JSON aren't treated as special.
  return readTemplate().replace(PAYLOAD_SENTINEL, () => json);
}

export function writeDashboard(
  spans: readonly TraceSpan[],
  outFile: string,
  meta: DashboardMeta = {},
  evals: readonly EvalRecord[] = [],
): string {
  mkdirSync(dirname(outFile), { recursive: true });
  writeFileSync(outFile, renderDashboard(spans, meta, evals), "utf-8");
  return outFile;
}

/**
 * Opens the given file in the default browser, unless running in CI or output isn't a TTY.
 * Best-effort and non-fatal - a headless/CI run just gets the file written and the path logged.
 */
export function maybeOpen(file: string): void {
  if (process.env["CI"] || process.env["NO_OPEN"] || !process.stdout.isTTY) return;
  const cmd = platform() === "darwin" ? "open" : platform() === "win32" ? "cmd" : "xdg-open";
  const args = platform() === "win32" ? ["/c", "start", "", file] : [file];
  try {
    spawn(cmd, args, { detached: true, stdio: "ignore" }).unref();
  } catch {
    /* opening is a convenience, never a hard failure */
  }
}
