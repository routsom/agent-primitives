/**
 * Human-in-the-loop approval gate (notes section 6-7, 12). Some tool calls are too consequential
 * to let a model make unsupervised - a payment, a destructive write, an email to a customer. The
 * gate lives in the harness, alongside scope and budgets, for the same reason those do: it's a
 * guarantee no prompt can route around. A gated tool cannot execute without an explicit
 * `approved` decision, full stop.
 *
 * The decision itself is a seam. `decide` may block awaiting a human (wire it to a queue + UI),
 * or read a decision recorded earlier - which is how this composes with durable execution: a
 * resolver that suspends the run, persists via the checkpoint store, and returns once a human
 * answers. The shipped default gates nothing, so existing runs are unchanged.
 */
export type ApprovalDecision = "approved" | "denied";

export interface ApprovalRequest {
  role: string;
  toolName: string;
  input: Record<string, unknown>;
  idempotencyKey: string;
  delegationDepth: number;
}

export interface ApprovalProvider {
  /** Does this (role, tool) pair require human approval before it may run? */
  requiresApproval(role: string, toolName: string): boolean;
  /** Resolve the decision. May block on a human or read a pre-recorded answer. */
  decide(request: ApprovalRequest): Promise<ApprovalDecision>;
}

/** Default: nothing needs approval - the harness behaves exactly as before. */
export class AutoApprove implements ApprovalProvider {
  requiresApproval(): boolean {
    return false;
  }
  async decide(): Promise<ApprovalDecision> {
    return "approved";
  }
}

/**
 * Gate a fixed set of tool names; delegate the actual approve/deny to an injected resolver (a
 * prompt, a web approval queue, a policy check). The resolver is where your product's HITL UX
 * lives; the gate just guarantees it's consulted.
 */
export class ToolApprovalGate implements ApprovalProvider {
  constructor(
    private readonly gatedTools: string[],
    private readonly resolver: (request: ApprovalRequest) => Promise<ApprovalDecision>,
  ) {}

  requiresApproval(_role: string, toolName: string): boolean {
    return this.gatedTools.includes(toolName);
  }

  decide(request: ApprovalRequest): Promise<ApprovalDecision> {
    return this.resolver(request);
  }
}
