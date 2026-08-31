import { describe, expect, it } from "vitest";
import { SummarizingCompactor, estimateTokens } from "../src/agents/compaction.js";
import type { ProviderMessage } from "../src/providers/types.js";

function history(n: number): ProviderMessage[] {
  const msgs: ProviderMessage[] = [{ role: "user", content: [{ type: "text", text: "ORIGINAL TASK" }] }];
  for (let i = 0; i < n; i++) {
    msgs.push({ role: "assistant", content: [{ type: "text", text: `turn ${i} `.repeat(50) }] });
  }
  msgs.push({ role: "assistant", content: [{ type: "text", text: "MOST RECENT" }] });
  return msgs;
}

describe("context compaction", () => {
  it("leaves history untouched below the token threshold", async () => {
    const compactor = new SummarizingCompactor({ thresholdTokens: 1_000_000, keepRecent: 2 });
    const msgs = history(20);
    expect(await compactor.maybeCompact(msgs)).toBe(msgs);
  });

  it("collapses the middle, preserving the original task and the recent tail", async () => {
    const msgs = history(40);
    const before = estimateTokens(msgs);
    const compactor = new SummarizingCompactor({ thresholdTokens: 100, keepRecent: 3 });
    const out = await compactor.maybeCompact(msgs);

    // Head (task) preserved, a summary inserted, tail kept: far fewer messages than before.
    expect(out.length).toBe(1 + 1 + 3);
    expect(out[0]).toEqual(msgs[0]);
    expect(out.at(-1)).toEqual(msgs.at(-1));
    expect(out[1]?.content[0]).toMatchObject({ type: "text" });
    expect((out[1]?.content[0] as { text: string }).text).toContain("[compacted context]");
    expect(estimateTokens(out)).toBeLessThan(before);
  });

  it("uses an injected summarizer when provided", async () => {
    const compactor = new SummarizingCompactor({
      thresholdTokens: 100,
      keepRecent: 2,
      summarize: () => "CUSTOM SUMMARY",
    });
    const out = await compactor.maybeCompact(history(30));
    expect((out[1]?.content[0] as { text: string }).text).toContain("CUSTOM SUMMARY");
  });
});
