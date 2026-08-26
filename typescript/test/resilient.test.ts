import { describe, expect, it } from "vitest";
import { ResilientChatModel } from "../src/providers/resilient.js";
import { ClassifiedError } from "../src/harness/errors.js";
import type { ChatCompletionRequest, ChatCompletionResult, ChatModel } from "../src/providers/types.js";

const okResult: ChatCompletionResult = {
  message: { role: "assistant", content: [{ type: "text", text: "ok" }] },
  usage: { inputTokens: 1, outputTokens: 1 },
  stopReason: "end_turn",
};

class ScriptedModel implements ChatModel {
  calls = 0;
  constructor(
    readonly provider: string,
    readonly model: string,
    private readonly script: (call: number) => ChatCompletionResult | Error,
  ) {}
  async complete(_request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    const outcome = this.script(this.calls++);
    if (outcome instanceof Error) throw outcome;
    return outcome;
  }
}

const noSleep = async () => {};

describe("resilient chat model", () => {
  it("retries a transient failure on the same model, then succeeds", async () => {
    const primary = new ScriptedModel("p", "m", (call) => (call < 2 ? new ClassifiedError("transient", "429 slow down") : okResult));
    const resilient = new ResilientChatModel(primary, { timeoutMs: 0, maxRetries: 2, baseDelayMs: 1, sleep: noSleep });
    const result = await resilient.complete({ messages: [] });
    expect(result.stopReason).toBe("end_turn");
    expect(primary.calls).toBe(3);
  });

  it("fails over to a fallback model after exhausting retries", async () => {
    const primary = new ScriptedModel("p", "m", () => new ClassifiedError("transient", "503 down"));
    const fallback = new ScriptedModel("f", "m2", () => okResult);
    const resilient = new ResilientChatModel(primary, { timeoutMs: 0, maxRetries: 1, baseDelayMs: 1, fallbacks: [fallback], sleep: noSleep });
    const result = await resilient.complete({ messages: [] });
    expect(result.stopReason).toBe("end_turn");
    expect(primary.calls).toBe(2); // initial + 1 retry
    expect(fallback.calls).toBe(1);
  });

  it("does NOT retry or fail over a non-transient error", async () => {
    const primary = new ScriptedModel("p", "m", () => new ClassifiedError("auth", "invalid api key"));
    const fallback = new ScriptedModel("f", "m2", () => okResult);
    const resilient = new ResilientChatModel(primary, { timeoutMs: 0, maxRetries: 3, baseDelayMs: 1, fallbacks: [fallback], sleep: noSleep });
    await expect(resilient.complete({ messages: [] })).rejects.toThrow("invalid api key");
    expect(primary.calls).toBe(1);
    expect(fallback.calls).toBe(0);
  });

  it("times out a hung call and classifies it transient (so it retries)", async () => {
    let resolved = 0;
    const primary: ChatModel = {
      provider: "p",
      model: "m",
      async complete() {
        resolved++;
        if (resolved === 1) return new Promise<ChatCompletionResult>(() => {}); // never resolves
        return okResult;
      },
    };
    const resilient = new ResilientChatModel(primary, { timeoutMs: 5, maxRetries: 1, baseDelayMs: 1, sleep: noSleep });
    const result = await resilient.complete({ messages: [] });
    expect(result.stopReason).toBe("end_turn");
    expect(resolved).toBe(2);
  });

  it("proxies the primary's provider and model identity", () => {
    const primary = new ScriptedModel("anthropic", "claude-sonnet-5", () => okResult);
    const resilient = new ResilientChatModel(primary, { timeoutMs: 0, maxRetries: 0, baseDelayMs: 1 });
    expect(resilient.provider).toBe("anthropic");
    expect(resilient.model).toBe("claude-sonnet-5");
  });
});
