import type { ProviderMessage } from "../providers/types.js";

/**
 * Context compaction (notes section 5). A long-running agent's message history grows until it
 * threatens the context window; compaction replaces the older middle of the conversation with a
 * short summary, keeping the original task and the most recent turns verbatim. It's a primitive a
 * prompt can't self-enforce - the agent can't summarize away messages it's already been sent - so
 * it lives in code, in the agent loop. It follows the same distill-to-a-reference philosophy as
 * the artifact store: carry a summary, not the raw blob.
 *
 * Off by default: `runAgent` only compacts when a Compactor is passed, so ordinary runs (and the
 * parity check) are unaffected. The `summarize` step is a seam - the shipped default is a
 * deterministic, non-LLM digest; wire an LLM call there when you want a semantic summary.
 */
export interface Compactor {
  maybeCompact(messages: ProviderMessage[]): Promise<ProviderMessage[]>;
}

export type Summarize = (messages: ProviderMessage[]) => Promise<string> | string;

export interface CompactionOptions {
  /** Compact once the estimated token size of the history exceeds this. */
  thresholdTokens: number;
  /** Number of most-recent messages kept verbatim (choose to land on a clean turn boundary). */
  keepRecent: number;
  /** How the compacted middle is summarized. Default: a deterministic, model-free digest. */
  summarize?: Summarize;
}

export class SummarizingCompactor implements Compactor {
  constructor(private readonly options: CompactionOptions) {}

  async maybeCompact(messages: ProviderMessage[]): Promise<ProviderMessage[]> {
    // Nothing to do until we're over budget and there's a middle to collapse.
    if (estimateTokens(messages) <= this.options.thresholdTokens) return messages;
    if (messages.length <= this.options.keepRecent + 1) return messages;

    const head = messages[0]!; // the original task - always preserved
    const middle = messages.slice(1, messages.length - this.options.keepRecent);
    const tail = messages.slice(messages.length - this.options.keepRecent);

    const summaryText = await (this.options.summarize ?? defaultSummarize)(middle);
    const summary: ProviderMessage = { role: "user", content: [{ type: "text", text: `[compacted context] ${summaryText}` }] };
    return [head, summary, ...tail];
  }
}

/** Model-free fallback summary: counts what was collapsed and keeps any final text. Deterministic. */
function defaultSummarize(messages: ProviderMessage[]): string {
  const toolCalls = messages.flatMap((m) => m.content.filter((b) => b.type === "tool_call")).length;
  const texts = messages
    .flatMap((m) => m.content.filter((b): b is Extract<ProviderMessage["content"][number], { type: "text" }> => b.type === "text"))
    .map((b) => b.text);
  const lastText = texts.at(-1) ?? "";
  return `${messages.length} earlier message(s) omitted (${toolCalls} tool call(s)). Last note: ${lastText.slice(0, 200)}`;
}

/** Cheap, provider-agnostic token estimate: ~4 chars/token over the serialized messages. */
export function estimateTokens(messages: ProviderMessage[]): number {
  return Math.ceil(JSON.stringify(messages).length / 4);
}
