import type { Tool, ToolRuntime } from "../tools/types.js";
import { AutoApprove, type ApprovalProvider } from "./approvals.js";
import { NoopAuditSink, redact, type AuditCorrelation, type AuditSink } from "./audit.js";
import { ToolCircuitBreaker, type CircuitBreakerOptions } from "./circuitBreaker.js";
import { AuthFailure, ClassifiedError, classifyError, ValidationFailure, type ToolOutcome } from "./errors.js";
import { IdempotencyCache } from "./idempotency.js";
import type { AgentRoleDef } from "./scope.js";
import { assertToolAllowed } from "./scope.js";

export * from "./approvals.js";
export * from "./scope.js";
export * from "./budget.js";
export * from "./idempotency.js";
export * from "./validate.js";
export * from "./schemas.js";
export * from "./errors.js";
export * from "./rateLimit.js";
export * from "./audit.js";
export * from "./circuitBreaker.js";

/**
 * Boundary guardrail seam (notes section 8, 19: "treat tool outputs as untrusted... sanitize
 * at every boundary"). A deterministic, non-LLM hook applied to content crossing a trust
 * boundary before it reaches the model. The default is identity - this ships the *seam* where
 * app-specific rules go (strip injected instructions, scrub PII, enforce allowed shapes), not
 * the rules themselves, which can't be generic. See docs/extending.md.
 */
export type Sanitizer = (boundary: "tool_output", content: unknown) => unknown;
const identitySanitizer: Sanitizer = (_boundary, content) => content;

export interface HarnessOptions {
  auditSink?: AuditSink;
  circuitBreaker?: Partial<CircuitBreakerOptions>;
  /** Applied to every tool's output before it returns to the model. Default: identity. */
  sanitize?: Sanitizer;
  /** Human-in-the-loop gate for consequential tools. Default: AutoApprove (gates nothing). */
  approvals?: ApprovalProvider;
}

export interface HarnessToolCall {
  idempotencyKey: string;
  toolName: string;
  input: Record<string, unknown>;
  delegationDepth: number;
  /** Correlation IDs for the audit log. When omitted, the audit entry uses empty ids. */
  correlation?: AuditCorrelation;
}

/**
 * Shared infrastructure every agent's tool call routes through - no agent-to-agent shortcut
 * around it (notes section 7). Validates scope, applies idempotency, executes, and returns a
 * typed ToolOutcome. Errors are classified here (transient/permanent/validation/auth) and
 * returned as data, never thrown into the agent loop - so the orchestrator applies retry and
 * escalation policy from a structured field, not from parsing a message string.
 */
export class Harness {
  private readonly tools = new Map<string, Tool>();
  private readonly idempotency = new IdempotencyCache();
  private readonly auditSink: AuditSink;
  private readonly breaker: ToolCircuitBreaker;
  private readonly sanitize: Sanitizer;
  private readonly approvals: ApprovalProvider;

  constructor(tools: Tool[], options: HarnessOptions = {}) {
    for (const tool of tools) this.tools.set(tool.name, tool);
    this.auditSink = options.auditSink ?? new NoopAuditSink();
    this.breaker = new ToolCircuitBreaker(options.circuitBreaker);
    this.sanitize = options.sanitize ?? identitySanitizer;
    this.approvals = options.approvals ?? new AutoApprove();
  }

  async execute(role: AgentRoleDef, call: HarnessToolCall, runtime: ToolRuntime): Promise<ToolOutcome> {
    const outcome = await this.run(role, call, runtime);
    // 100%-coverage audit record, emitted for EVERY tool call regardless of outcome. Params
    // are redacted at this point of logging, never stored raw (notes section 22).
    this.auditSink.record({
      timestamp: new Date().toISOString(),
      traceId: call.correlation?.traceId ?? "",
      sessionId: call.correlation?.sessionId ?? "",
      requestId: call.correlation?.requestId ?? "",
      agentRole: role.role,
      toolName: call.toolName,
      idempotencyKey: call.idempotencyKey,
      delegationDepth: call.delegationDepth,
      paramsRedacted: redact(call.input) as Record<string, unknown>,
      resultStatus: outcome.status,
      ...(outcome.status !== "ok" ? { errorType: outcome.error.type } : {}),
    });
    return outcome;
  }

  private async run(role: AgentRoleDef, call: HarnessToolCall, runtime: ToolRuntime): Promise<ToolOutcome> {
    // Pre-execution refusals classify as `rejected` (the harness said no, the tool never ran).
    try {
      assertToolAllowed(role, call.toolName);
    } catch (error) {
      return { status: "rejected", error: classifyError(error) };
    }

    const tool = this.tools.get(call.toolName);
    if (!tool) {
      return { status: "rejected", error: classifyError(new ValidationFailure(`harness: unknown tool "${call.toolName}"`)) };
    }

    // Circuit breaker: if this tool's backend is failing system-wide, short-circuit
    // immediately as a transient error rather than piling on another timeout.
    if (this.breaker.isOpen(call.toolName)) {
      return { status: "rejected", error: classifyError(new ClassifiedError("transient", `tool "${call.toolName}" circuit is open`)) };
    }

    // Human-in-the-loop gate: a consequential tool cannot run without an explicit approval. A
    // denial is an authorization decision (classifies as `auth`: no retry, security-logged), so
    // the tool never executes. Pre-execution, so it counts as `rejected`, not `error`.
    if (this.approvals.requiresApproval(role.role, call.toolName)) {
      const decision = await this.approvals.decide({
        role: role.role,
        toolName: call.toolName,
        input: call.input,
        idempotencyKey: call.idempotencyKey,
        delegationDepth: call.delegationDepth,
      });
      if (decision !== "approved") {
        return { status: "rejected", error: classifyError(new AuthFailure(`tool "${call.toolName}" denied by approval gate`)) };
      }
    }

    // Post-execution failures classify as `error` (the tool ran and threw).
    try {
      const output = await this.idempotency.run(call.idempotencyKey, () =>
        tool.execute(call.input, {
          agentRole: role.role,
          delegationDepth: call.delegationDepth,
          runtime,
        }),
      );
      this.breaker.recordSuccess(call.toolName);
      return { status: "ok", output: this.sanitize("tool_output", output) };
    } catch (error) {
      this.breaker.recordFailure(call.toolName);
      return { status: "error", error: classifyError(error) };
    }
  }

  toolDefinitions(role: AgentRoleDef): { name: string; description: string; inputSchema: Record<string, unknown> }[] {
    return role.allowedTools
      .map((name) => this.tools.get(name))
      .filter((tool): tool is Tool => Boolean(tool))
      .map((tool) => ({ name: tool.name, description: tool.description, inputSchema: tool.inputSchema }));
  }
}
