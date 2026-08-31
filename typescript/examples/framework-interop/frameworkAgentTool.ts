import type { Tool } from "../../src/tools/types.js";
import { invokeExternalFrameworkAgent } from "./externalFrameworkAgent.js";

/**
 * The whole interop story in one adapter: a foreign framework agent, exposed to *our* lead
 * agent as a single tool. Because it is an ordinary `Tool`, every call to it routes through the
 * harness like any other - it inherits tool scoping, the per-agent tool-call budget, the
 * idempotency cache, the circuit breaker, deterministic error classification, and a trace span.
 * The framework runs its own control loop *inside* `execute`; it never gets to run *ours*.
 *
 * Two discipline points this example deliberately keeps (see CLAUDE.md):
 *   1. Distill, don't dump. The framework returns a verbose transcript; we return a short
 *      summary + answer, not the raw chatter. In a full run you'd persist the transcript via
 *      ctx.runtime.writeArtifact and return the ArtifactRef instead of inlining it.
 *   2. Let errors surface as classified data. We let the framework's exception propagate; the
 *      harness turns it into a typed ToolError (transient vs. permanent) so the orchestrator,
 *      not the model, decides whether to retry.
 */
export function createFrameworkAgentTool(failMode?: "transient" | "permanent"): Tool<{ task: string }, { summary: string; answer: string }> {
  return {
    name: "framework_agent",
    description:
      "Delegate a research task to an external framework-based agent (e.g. a LangGraph graph or CrewAI crew). Returns a distilled summary and final answer.",
    inputSchema: {
      type: "object",
      required: ["task"],
      properties: { task: { type: "string" } },
    },
    exposable: true,
    async execute(input) {
      const out = await invokeExternalFrameworkAgent({ task: input.task }, failMode);
      // Distill: collapse the framework's internal transcript to a one-line provenance summary.
      return {
        summary: `external framework agent ran ${out.transcript.length} internal steps`,
        answer: out.answer,
      };
    },
  };
}
