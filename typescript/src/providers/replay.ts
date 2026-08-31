import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { ClassifiedError } from "../harness/errors.js";
import type { ChatCompletionRequest, ChatCompletionResult, ChatModel } from "./types.js";

/**
 * Deterministic replay ("VCR") for the model dependency. Wraps a ChatModel and, keyed by a hash
 * of each request, records the response to a cassette file - then replays it on the next run
 * without touching the network. This is what makes the "every layer is inspectable" claim
 * *testable*: capture one real run, then regression-test the orchestration logic offline, for
 * free, and reproduce a production failure exactly. Because it's a ChatModel itself, nothing
 * above the provider layer knows replay is happening - it's a decorator, like ResilientChatModel.
 *
 * Modes:
 *  - "auto"   (default): replay a request that's in the cassette; otherwise call the base model
 *             and record it. The everyday mode - a missing cassette records itself on first run.
 *  - "replay": replay only; a request not in the cassette throws. Use in CI to guarantee no
 *             network call sneaks in and the recording is complete.
 *  - "record": always call the base model and (re)record. Use to refresh a cassette.
 */
export type ReplayMode = "auto" | "replay" | "record";

export interface ReplayOptions {
  cassettePath: string;
  mode?: ReplayMode;
}

interface CassetteEntry {
  provider: string;
  model: string;
  request: ChatCompletionRequest;
  response: ChatCompletionResult;
}

/** Stable hash of the semantically-relevant request fields. Order-independent for object keys. */
export function requestHash(provider: string, model: string, request: ChatCompletionRequest): string {
  const canonical = stableStringify({ provider, model, system: request.system ?? "", messages: request.messages, tools: request.tools ?? [] });
  return createHash("sha256").update(canonical).digest("hex").slice(0, 32);
}

export class ReplayChatModel implements ChatModel {
  private readonly mode: ReplayMode;
  private cassette: Record<string, CassetteEntry>;

  constructor(
    private readonly base: ChatModel,
    private readonly options: ReplayOptions,
  ) {
    this.mode = options.mode ?? "auto";
    this.cassette = this.load();
  }

  get provider(): string {
    return this.base.provider;
  }

  get model(): string {
    return this.base.model;
  }

  async complete(request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    const key = requestHash(this.base.provider, this.base.model, request);
    const recorded = this.cassette[key];

    if (this.mode !== "record" && recorded) return recorded.response;
    if (this.mode === "replay") {
      throw new ClassifiedError("permanent", `replay: no cassette entry for request ${key} in ${this.options.cassettePath} (run in "record" or "auto" mode first)`);
    }

    const response = await this.base.complete(request);
    this.cassette[key] = { provider: this.base.provider, model: this.base.model, request, response };
    this.save();
    return response;
  }

  private load(): Record<string, CassetteEntry> {
    try {
      return JSON.parse(readFileSync(this.options.cassettePath, "utf-8")) as Record<string, CassetteEntry>;
    } catch {
      return {};
    }
  }

  private save(): void {
    mkdirSync(dirname(this.options.cassettePath), { recursive: true });
    writeFileSync(this.options.cassettePath, JSON.stringify(this.cassette, null, 2), "utf-8");
  }
}

/** JSON.stringify with object keys sorted recursively, so equivalent requests hash identically. */
function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b));
    return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${stableStringify(v)}`).join(",")}}`;
  }
  return JSON.stringify(value ?? null);
}
