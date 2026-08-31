import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ReplayChatModel } from "../src/providers/replay.js";
import type { ChatCompletionRequest, ChatCompletionResult, ChatModel } from "../src/providers/types.js";

/** A base model that counts how many times it was actually called, and returns a per-call answer. */
class CountingModel implements ChatModel {
  readonly provider = "mock";
  readonly model = "counting-1";
  calls = 0;
  async complete(_request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    this.calls += 1;
    return {
      message: { role: "assistant", content: [{ type: "text", text: `answer #${this.calls}` }] },
      usage: { inputTokens: 10, outputTokens: 5 },
      stopReason: "end_turn",
    };
  }
}

const req = (text: string): ChatCompletionRequest => ({ system: "s", messages: [{ role: "user", content: [{ type: "text", text }] }] });

describe("deterministic replay (VCR)", () => {
  let dir: string;
  let cassettePath: string;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "replay-"));
    cassettePath = join(dir, "cassette.json");
  });
  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("records on first call and replays without hitting the base model", async () => {
    const base = new CountingModel();
    const first = new ReplayChatModel(base, { cassettePath });
    const recorded = await first.complete(req("hello"));
    expect(base.calls).toBe(1);

    // A fresh decorator over a fresh base loads the cassette from disk: same answer, zero calls.
    const base2 = new CountingModel();
    const replayed = new ReplayChatModel(base2, { cassettePath });
    const out = await replayed.complete(req("hello"));
    expect(out).toEqual(recorded);
    expect(base2.calls).toBe(0);
  });

  it("distinguishes different requests by hash", async () => {
    const base = new CountingModel();
    const vcr = new ReplayChatModel(base, { cassettePath });
    const a = await vcr.complete(req("query A"));
    const b = await vcr.complete(req("query B"));
    expect(base.calls).toBe(2);
    expect(a.message.content).not.toEqual(b.message.content);
    // Replaying A returns A's recording, not B's.
    expect((await vcr.complete(req("query A"))).message).toEqual(a.message);
    expect(base.calls).toBe(2);
  });

  it("replay-only mode throws on a cassette miss", async () => {
    const vcr = new ReplayChatModel(new CountingModel(), { cassettePath, mode: "replay" });
    await expect(vcr.complete(req("never recorded"))).rejects.toThrow(/no cassette entry/);
  });
});
