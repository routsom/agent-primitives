/**
 * Sliding-window rate limiter (notes section 19: "rate limiting at every layer"). Reject
 * abusive or runaway traffic at the earliest possible point - before the model ever runs -
 * because the cost of rejecting early is near zero while the cost of processing then rejecting
 * is a full model call. Keyed by caller identity (auth token, or remote address as a fallback).
 *
 * In-memory by design for the boilerplate: a single process. For multi-instance deployments,
 * back the same interface with a shared store (Redis) - see docs/extending.md.
 */
export class SlidingWindowRateLimiter {
  private readonly hits = new Map<string, number[]>();

  constructor(
    private readonly maxRequests: number,
    private readonly windowMs: number,
  ) {}

  /** Returns true if the request is allowed (and records it); false if the caller is over the limit. */
  tryAcquire(key: string, now: number = Date.now()): boolean {
    const cutoff = now - this.windowMs;
    const recent = (this.hits.get(key) ?? []).filter((t) => t > cutoff);
    if (recent.length >= this.maxRequests) {
      this.hits.set(key, recent);
      return false;
    }
    recent.push(now);
    this.hits.set(key, recent);
    return true;
  }
}
