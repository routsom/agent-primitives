/** Repeated calls with the same idempotency key resolve to the single first result (specs/schemas/tool-envelope.schema.json). */
export class IdempotencyCache {
  private readonly inFlight = new Map<string, Promise<unknown>>();

  async run<T>(key: string, fn: () => Promise<T>): Promise<T> {
    const existing = this.inFlight.get(key);
    if (existing) return existing as Promise<T>;
    const promise = fn();
    this.inFlight.set(key, promise);
    try {
      return await promise;
    } catch (error) {
      this.inFlight.delete(key);
      throw error;
    }
  }
}
