import type { TraceSpan } from "../tracing/tracer.js";

/**
 * Per-run cost ledger. `RunBudget` caps token *count*; the profiler shows a live dollar gauge;
 * this is the after-the-fact accounting in between - it turns the `costUsd` every model_call span
 * already carries into a total plus a breakdown by model and by agent role, so "what did this run
 * cost, and where?" is one function call, not a spreadsheet. It reads the trace the run already
 * emitted, so it adds no instrumentation and no extra model calls (notes section 8, 11).
 */
export interface CostLine {
  calls: number;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export interface CostSummary {
  total: CostLine;
  byModel: Record<string, CostLine>;
  byAgent: Record<string, CostLine>;
}

const emptyLine = (): CostLine => ({ calls: 0, inputTokens: 0, outputTokens: 0, costUsd: 0 });

function add(line: CostLine, span: TraceSpan): void {
  line.calls += 1;
  line.inputTokens += span.tokenUsage?.inputTokens ?? 0;
  line.outputTokens += span.tokenUsage?.outputTokens ?? 0;
  line.costUsd += span.costUsd ?? 0;
}

/** Reduce a run's spans to a cost summary. Only `model_call` spans carry spend. */
export function summarizeCost(spans: readonly TraceSpan[]): CostSummary {
  const summary: CostSummary = { total: emptyLine(), byModel: {}, byAgent: {} };
  for (const span of spans) {
    if (span.kind !== "model_call") continue;
    const model = (span.attributes?.["model"] as string | undefined) ?? "unknown";
    const agent = span.agentRole ?? "unknown";
    add(summary.total, span);
    add((summary.byModel[model] ??= emptyLine()), span);
    add((summary.byAgent[agent] ??= emptyLine()), span);
  }
  return summary;
}

/** A compact, human-readable rendering of a cost summary for a CLI or a log line. */
export function formatCostSummary(summary: CostSummary): string {
  const usd = (n: number) => `$${n.toFixed(6)}`;
  const line = (label: string, l: CostLine) => `  ${label.padEnd(24)} ${String(l.calls).padStart(3)} calls  ${String(l.inputTokens + l.outputTokens).padStart(8)} tok  ${usd(l.costUsd)}`;
  const rows: string[] = [`Run cost: ${usd(summary.total.costUsd)} over ${summary.total.calls} model call(s)`];
  rows.push("by model:");
  for (const [model, l] of Object.entries(summary.byModel)) rows.push(line(model, l));
  rows.push("by agent:");
  for (const [agent, l] of Object.entries(summary.byAgent)) rows.push(line(agent, l));
  return rows.join("\n");
}
