/**
 * Per-tool, system-wide circuit breaker (notes section 12: "a circuit breaker per tool,
 * system-wide - not per conversation"). If a tool's failure rate spikes across all sessions,
 * the harness marks it unavailable and short-circuits future calls immediately, instead of
 * every concurrent conversation independently timing out on the same broken backend.
 *
 * This is distinct from the per-subagent retry cap (which bounds one agent's retries of one
 * call) and from provider resilience (which handles the *model* being down). This handles a
 * *tool's backend* being down.
 */
export interface CircuitBreakerOptions {
  /** Consecutive-ish failures within the window that trip the breaker open. */
  failureThreshold: number;
  /** Rolling window over which failures are counted. */
  windowMs: number;
  /** How long the breaker stays open before allowing a trial call again. */
  cooldownMs: number;
}

const DEFAULTS: CircuitBreakerOptions = { failureThreshold: 5, windowMs: 60_000, cooldownMs: 30_000 };

interface ToolState {
  failures: number[];
  openedAt?: number;
}

export class ToolCircuitBreaker {
  private readonly state = new Map<string, ToolState>();
  private readonly options: CircuitBreakerOptions;

  constructor(options: Partial<CircuitBreakerOptions> = {}) {
    this.options = { ...DEFAULTS, ...options };
  }

  /** True if calls to this tool should be short-circuited right now. */
  isOpen(toolName: string, now: number = Date.now()): boolean {
    const s = this.state.get(toolName);
    if (s?.openedAt === undefined) return false;
    if (now - s.openedAt >= this.options.cooldownMs) {
      // Cooldown elapsed: half-open - clear state and allow a trial call through.
      this.state.delete(toolName);
      return false;
    }
    return true;
  }

  recordSuccess(toolName: string): void {
    this.state.delete(toolName);
  }

  recordFailure(toolName: string, now: number = Date.now()): void {
    const s = this.state.get(toolName) ?? { failures: [] };
    s.failures = s.failures.filter((t) => t > now - this.options.windowMs);
    s.failures.push(now);
    if (s.failures.length >= this.options.failureThreshold) s.openedAt = now;
    this.state.set(toolName, s);
  }
}
