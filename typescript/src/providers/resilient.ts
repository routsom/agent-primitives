import { classifyError, ClassifiedError } from "../harness/errors.js";
import type { ChatCompletionRequest, ChatCompletionResult, ChatModel } from "./types.js";

export interface ResilienceOptions {
  /** Per-call wall-clock timeout. A timeout classifies as transient (so it retries / fails over). */
  timeoutMs: number;
  /** Retries on the *same* model for transient failures before failing over to the next. */
  maxRetries: number;
  /** Exponential backoff base: delay = baseDelayMs * 2^attempt, with jitter. */
  baseDelayMs: number;
  /** Ordered fallback models tried after the primary exhausts its retries on a transient failure. */
  fallbacks?: ChatModel[];
  /** Injectable sleep, so tests don't wait on real backoff. */
  sleep?: (ms: number) => Promise<void>;
}

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Infrastructure-level resilience for the model dependency (notes section 15: "a 429/529 means
 * the model never ran at all... needs its own handling: retry with backoff, and ideally a
 * configured fallback to another model/region"). Wraps a primary ChatModel and, transparently:
 *
 *  - times out a hung call (classified transient),
 *  - retries transient failures on the same model with exponential backoff,
 *  - fails over to the next configured fallback model when retries are exhausted,
 *  - re-raises non-transient errors (validation/auth/permanent) immediately - no point retrying
 *    or failing over a request the backend will reject the same way every time.
 *
 * This is deliberately a ChatModel itself, so nothing above the provider layer knows or cares
 * that resilience is happening - it's a decorator, not a new abstraction.
 */
export class ResilientChatModel implements ChatModel {
  private readonly chain: ChatModel[];
  private readonly sleep: (ms: number) => Promise<void>;

  constructor(
    private readonly primary: ChatModel,
    private readonly options: ResilienceOptions,
  ) {
    this.chain = [primary, ...(options.fallbacks ?? [])];
    this.sleep = options.sleep ?? defaultSleep;
  }

  get provider(): string {
    return this.primary.provider;
  }

  get model(): string {
    return this.primary.model;
  }

  async complete(request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    let lastError: unknown;

    for (const model of this.chain) {
      for (let attempt = 0; attempt <= this.options.maxRetries; attempt++) {
        try {
          return await this.withTimeout(model.complete(request));
        } catch (error) {
          lastError = error;
          const classified = classifyError(error);
          // Only transient errors are worth retrying or failing over. Everything else (bad
          // request, auth, not-found) will fail identically, so surface it immediately.
          if (classified.type !== "transient") throw error;
          if (attempt < this.options.maxRetries) {
            await this.sleep(this.backoff(attempt));
          }
        }
      }
      // Retries on this model exhausted - fall through to the next fallback in the chain.
    }

    throw lastError;
  }

  private backoff(attempt: number): number {
    const base = this.options.baseDelayMs * 2 ** attempt;
    return base + Math.floor(Math.random() * this.options.baseDelayMs);
  }

  private async withTimeout(promise: Promise<ChatCompletionResult>): Promise<ChatCompletionResult> {
    if (this.options.timeoutMs <= 0) return promise;
    let timer: ReturnType<typeof setTimeout>;
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new ClassifiedError("transient", `model call timed out after ${this.options.timeoutMs}ms`)), this.options.timeoutMs);
    });
    try {
      return await Promise.race([promise, timeout]);
    } finally {
      clearTimeout(timer!);
    }
  }
}
