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
