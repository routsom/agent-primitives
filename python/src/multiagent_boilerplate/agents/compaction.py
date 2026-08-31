"""Context compaction (notes section 5). A long-running agent's message history grows until it
threatens the context window; compaction replaces the older middle of the conversation with a
short summary, keeping the original task and the most recent turns verbatim. It's a primitive a
prompt can't self-enforce - the agent can't summarize away messages it's already been sent - so it
lives in code, in the agent loop, following the same distill-to-a-reference philosophy as the
artifact store: carry a summary, not the raw blob.

Off by default: run_agent only compacts when a Compactor is passed, so ordinary runs (and the
parity check) are unaffected. The `summarize` step is a seam - the shipped default is a
deterministic, non-LLM digest; wire an LLM call there when you want a semantic summary.
Mirrors typescript/src/agents/compaction.ts."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Protocol, runtime_checkable

from ..providers.types import ProviderMessage, TextBlock, ToolCallBlock

Summarize = Callable[[list[ProviderMessage]], Awaitable[str] | str]


@runtime_checkable
class Compactor(Protocol):
    async def maybe_compact(self, messages: list[ProviderMessage]) -> list[ProviderMessage]: ...


class SummarizingCompactor:
    def __init__(self, threshold_tokens: int, keep_recent: int, summarize: Summarize | None = None) -> None:
        self._threshold_tokens = threshold_tokens
        self._keep_recent = keep_recent
        self._summarize = summarize or _default_summarize

    async def maybe_compact(self, messages: list[ProviderMessage]) -> list[ProviderMessage]:
        # Nothing to do until we're over budget and there's a middle to collapse.
        if estimate_tokens(messages) <= self._threshold_tokens:
            return messages
        if len(messages) <= self._keep_recent + 1:
            return messages

        head = messages[0]  # the original task - always preserved
        middle = messages[1 : len(messages) - self._keep_recent]
        tail = messages[len(messages) - self._keep_recent :]

        result = self._summarize(middle)
        summary_text = await result if hasattr(result, "__await__") else result
        summary = ProviderMessage(role="user", content=[TextBlock(text=f"[compacted context] {summary_text}")])
        return [head, summary, *tail]


def _default_summarize(messages: list[ProviderMessage]) -> str:
    """Model-free fallback: counts what was collapsed and keeps any final text. Deterministic."""
    tool_calls = sum(1 for m in messages for b in m.content if isinstance(b, ToolCallBlock))
    texts = [b.text for m in messages for b in m.content if isinstance(b, TextBlock)]
    last_text = texts[-1] if texts else ""
    return f"{len(messages)} earlier message(s) omitted ({tool_calls} tool call(s)). Last note: {last_text[:200]}"


def estimate_tokens(messages: list[ProviderMessage]) -> int:
    """Cheap, provider-agnostic token estimate: ~4 chars/token over the serialized messages."""
    serialized = json.dumps([asdict(m) for m in messages])
    return -(-len(serialized) // 4)  # ceil division
