import type { ChatModel, ContentBlock, ProviderMessage } from "../providers/types.js";
import type { Harness } from "../harness/index.js";
import { RunBudget, ToolCallBudget, classifyError, loadAgentRole, loadPrompt, type ToolError, type ToolOutcome } from "../harness/index.js";
import type { AgentRoleDef } from "../harness/scope.js";
import type { ToolRuntime } from "../tools/types.js";
import type { Tracer } from "../tracing/tracer.js";
import { computeCostUsd } from "../cost/pricing.js";
import { deriveReviewFlags } from "./review.js";
import type { AgentResult } from "./types.js";

/**
 * The error shape the *model* sees. Auth failures are redacted to "not permitted" - the model
 * gets no detail about why, while the audit trail keeps the real message (notes section 12).
 */
function modelFacingError(outcome: Extract<ToolOutcome, { status: "error" | "rejected" }>): Record<string, unknown> {
  const { type, retryable, code } = outcome.error;
  const message = type === "auth" ? "not permitted" : outcome.error.message;
  return { status: outcome.status, error: { type, message, retryable, ...(code ? { code } : {}) } };
}

export interface RunAgentParams {
  roleName: string;
  userPrompt: string;
  model: ChatModel;
  harness: Harness;
  runtime: ToolRuntime;
  tracer: Tracer;
  taskId: string;
  delegationDepth: number;
  parentSpanId?: string | null;
  /** Appended to the role's base system prompt, e.g. "Objective: ...\nOutput format: ..." for a subagent's specific task. */
  extraSystemContext?: string;
  /** Caps how many tool-use turns the loop will take even if the budget config is larger - a hard backstop against infinite loops. */
  maxTurns?: number;
  /** Shared across the whole run (lead + every subagent). When exhausted, the agent stops before its next model call. */
  runBudget?: RunBudget;
}

/**
 * The generic agent loop every role (lead, subagent, citation, judge) runs through. Not
 * role-specific logic - that lives entirely in specs/prompts and specs/agents. This function
 * is the harness-enforced tool-use loop: call model, execute any requested tool calls through
 * the harness, feed results back, repeat until the model stops requesting tools.
 */
export async function runAgent(params: RunAgentParams): Promise<AgentResult> {
  const role = loadAgentRole(params.roleName) as unknown as AgentRoleDef & { promptFile: string };
  const systemPrompt = loadPrompt(role.promptFile) + (params.extraSystemContext ? `\n\n---\n\n${params.extraSystemContext}` : "");
  const budget = new ToolCallBudget(role.role, role.budget.maxToolCalls);
  const maxTurns = params.maxTurns ?? role.budget.maxToolCalls + 2;

  const messages: ProviderMessage[] = [{ role: "user", content: [{ type: "text", text: params.userPrompt }] }];
  const artifactRefs: AgentResult["artifactRefs"] = [];
  // Errors returned to the model but not subsequently recovered from feed the deterministic
  // needs_review derivation (notes section 16a). Tracked here, evaluated at return.
  const unrecoveredErrors: ToolError[] = [];

  const agentSpan = params.tracer.startSpan("agent", `${role.role}:${params.taskId}`, {
    parentSpanId: params.parentSpanId ?? null,
    agentRole: role.role,
    delegationDepth: params.delegationDepth,
  });

  // Builds the AgentResult and attaches the deterministically-derived review flags.
  const finish = (
    status: AgentResult["status"],
    text: string,
    lastStopReason?: "end_turn" | "tool_use" | "max_tokens",
  ): AgentResult => {
    const reviewFlags = deriveReviewFlags({ status, unrecoveredErrors, finalText: text, ...(lastStopReason ? { lastStopReason } : {}) });
    return { taskId: params.taskId, role: role.role, text, artifactRefs, status, needsReview: reviewFlags.length > 0, reviewFlags };
  };

  for (let turn = 0; turn < maxTurns; turn++) {
    // Session-level cost ceiling, checked before spend. Distinct from the per-agent tool-call
    // cap and the delegation-depth cap - this bounds total tokens across the whole swarm.
    if (params.runBudget?.isExhausted()) {
      params.tracer.endSpan(agentSpan, "partial", { attributes: { stoppedReason: "run_budget_exhausted" } });
      return finish("partial", "(stopped: run token budget exhausted)");
    }

    const modelSpan = params.tracer.startSpan("model_call", `${role.role} turn ${turn}`, {
      parentSpanId: agentSpan.spanId,
      agentRole: role.role,
      delegationDepth: params.delegationDepth,
    });

    const result = await params.model.complete({
      system: systemPrompt,
      messages,
      tools: params.harness.toolDefinitions(role),
    });
    params.runBudget?.record(result.usage);
    const costUsd = computeCostUsd(params.model.provider, params.model.model, result.usage);
    params.tracer.endSpan(modelSpan, "ok", { tokenUsage: result.usage, costUsd });
    messages.push(result.message);

    if (result.stopReason !== "tool_use") {
      params.tracer.endSpan(agentSpan, "ok");
      return finish("ok", textOf(result.message), result.stopReason);
    }

    const toolCalls = result.message.content.filter((b): b is Extract<ContentBlock, { type: "tool_call" }> => b.type === "tool_call");
    const toolResults: ContentBlock[] = [];

    for (const call of toolCalls) {
      const toolSpan = params.tracer.startSpan("tool_call", call.name, {
        parentSpanId: agentSpan.spanId,
        agentRole: role.role,
        delegationDepth: params.delegationDepth,
      });

      // Exhausting the per-agent tool-call budget is a harness guarantee, not a tool failure:
      // the harness forces a terminal `rejected` outcome regardless of what the model wants next.
      let outcome: ToolOutcome;
      try {
        budget.consume();
        outcome = await params.harness.execute(
          role,
          {
            idempotencyKey: call.id,
            toolName: call.name,
            input: call.input,
            delegationDepth: params.delegationDepth,
            // trace_id / session_id share the tracer instance (one per run here); request_id is
            // this agent invocation. In a multi-turn conversation you'd rotate the tracer per turn.
            correlation: { traceId: params.tracer.traceId, sessionId: params.tracer.traceId, requestId: params.taskId },
          },
          params.runtime,
        );
      } catch (budgetError) {
        outcome = { status: "rejected", error: classifyError(budgetError) };
      }

      if (outcome.status === "ok") {
        params.tracer.endSpan(toolSpan, "ok");
        if (call.name === "write_artifact") artifactRefs.push(outcome.output as AgentResult["artifactRefs"][number]);
        toolResults.push({ type: "tool_result", toolCallId: call.id, output: outcome.output });
      } else {
        unrecoveredErrors.push(outcome.error);
        params.tracer.endSpan(toolSpan, "error", {
          attributes: { errorType: outcome.error.type, retryable: outcome.error.retryable, code: outcome.error.code ?? null },
        });
        toolResults.push({ type: "tool_result", toolCallId: call.id, output: modelFacingError(outcome), isError: true });
      }
    }

    messages.push({ role: "tool", content: toolResults });
  }

  params.tracer.endSpan(agentSpan, "partial");
  return finish("partial", "(stopped: exceeded max turns before reaching a final answer)");
}

function textOf(message: ProviderMessage): string {
  return message.content
    .filter((b): b is Extract<ContentBlock, { type: "text" }> => b.type === "text")
    .map((b) => b.text)
    .join("\n");
}
