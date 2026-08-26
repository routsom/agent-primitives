import type { ToolError } from "../harness/index.js";

export interface ReviewSignals {
  status: "ok" | "partial" | "error";
  unrecoveredErrors: ToolError[];
  finalText: string;
  /** Stop reason of the final model call, if the loop ended on the model (not on a cap). */
  lastStopReason?: "end_turn" | "tool_use" | "max_tokens";
}

/**
 * Structural checks on the trace that just completed (notes section 16a: "what actually sets
 * needs_review: true - not the LLM judge"). Every check reads a field the run already produced;
 * none costs an extra inference. The judge, if run, is triggered *by* these flags rather than
 * being what sets them - so the expensive path only fires on runs a cheap check already flagged.
 */
export function deriveReviewFlags(signals: ReviewSignals): string[] {
  const flags: string[] = [];

  if (signals.status === "partial") flags.push("partial_completion");
  if (signals.status === "error") flags.push("errored");

  // One flag per distinct unrecovered error type (auth failures are always worth a look).
  const errorTypes = new Set(signals.unrecoveredErrors.map((e) => e.type));
  for (const type of errorTypes) flags.push(`unrecovered_tool_error:${type}`);

  if (signals.lastStopReason === "max_tokens") flags.push("max_tokens_truncation");

  // An "ok" run that produced almost no text is suspicious - the model may have bailed.
  if (signals.status === "ok" && signals.finalText.trim().length < 20) flags.push("empty_response");

  return flags;
}
