/** Two circuit breakers, tracked separately (notes section 8-9): runaway spawning vs. runaway retrying. */

export class DelegationDepthExceededError extends Error {
  constructor(depth: number, cap: number) {
    super(`delegation depth ${depth} exceeds cap ${cap} - rejecting further spawning`);
  }
}

export class SubagentCountExceededError extends Error {
  constructor(count: number, cap: number) {
    super(`requested ${count} subagents, exceeds per-call cap ${cap}`);
  }
}

export class ToolCallBudgetExceededError extends Error {
  constructor(role: string, cap: number) {
    super(`role "${role}" exceeded its tool-call budget of ${cap} for this task`);
  }
}

export function assertDepthWithinCap(depth: number, cap: number): void {
  if (depth > cap) throw new DelegationDepthExceededError(depth, cap);
}

export function assertSubagentCountWithinCap(count: number, cap: number): void {
  if (count > cap) throw new SubagentCountExceededError(count, cap);
}

export class ToolCallBudget {
  private used = 0;
  constructor(
    private readonly role: string,
    private readonly cap: number,
  ) {}

  consume(): void {
    this.used += 1;
    if (this.used > this.cap) throw new ToolCallBudgetExceededError(this.role, this.cap);
  }

  get remaining(): number {
    return Math.max(0, this.cap - this.used);
  }
}

export class RunBudgetExceededError extends Error {
  constructor(consumed: number, cap: number) {
    super(`run token budget exhausted: consumed ${consumed} tokens, ceiling is ${cap}`);
  }
}

/**
 * Session-level cost/token ceiling shared across the *entire* run - the lead agent and every
 * subagent it spawns count against one budget (notes section 15: "a session-level cost/token
 * budget as a circuit breaker distinct from any single tool's retry policy"). This is what
 * stops a runaway swarm from spending unbounded tokens even when every individual per-agent
 * and per-tool cap is still within limits. One instance per run, threaded through the whole
 * tree. A ceiling of 0 (or negative) means unlimited.
 */
export class RunBudget {
  private consumedTokens = 0;
  constructor(private readonly maxTokens: number) {}

  record(usage: { inputTokens: number; outputTokens: number }): void {
    this.consumedTokens += usage.inputTokens + usage.outputTokens;
  }

  /** True once the ceiling is reached - checked before each model call, which is where spend happens. */
  isExhausted(): boolean {
    return this.maxTokens > 0 && this.consumedTokens >= this.maxTokens;
  }

  assertWithinCeiling(): void {
    if (this.isExhausted()) throw new RunBudgetExceededError(this.consumedTokens, this.maxTokens);
  }

  get consumed(): number {
    return this.consumedTokens;
  }
}
