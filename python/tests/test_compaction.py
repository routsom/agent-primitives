"""Context compaction: collapse the older middle of a long history to a summary, off by default."""

from __future__ import annotations

from multiagent_boilerplate.agents.compaction import SummarizingCompactor, estimate_tokens
from multiagent_boilerplate.providers.types import ProviderMessage, TextBlock


def _history(n: int) -> list[ProviderMessage]:
    msgs = [ProviderMessage(role="user", content=[TextBlock(text="ORIGINAL TASK")])]
    for i in range(n):
        msgs.append(ProviderMessage(role="assistant", content=[TextBlock(text=f"turn {i} " * 50)]))
    msgs.append(ProviderMessage(role="assistant", content=[TextBlock(text="MOST RECENT")]))
    return msgs


async def test_below_threshold_is_untouched() -> None:
    compactor = SummarizingCompactor(threshold_tokens=1_000_000, keep_recent=2)
    msgs = _history(20)
    assert await compactor.maybe_compact(msgs) is msgs


async def test_collapses_middle_preserving_task_and_recent_tail() -> None:
    msgs = _history(40)
    before = estimate_tokens(msgs)
    compactor = SummarizingCompactor(threshold_tokens=100, keep_recent=3)
    out = await compactor.maybe_compact(msgs)

    assert len(out) == 1 + 1 + 3
    assert out[0] == msgs[0]
    assert out[-1] == msgs[-1]
    assert isinstance(out[1].content[0], TextBlock)
    assert "[compacted context]" in out[1].content[0].text
    assert estimate_tokens(out) < before


async def test_uses_injected_summarizer() -> None:
    compactor = SummarizingCompactor(threshold_tokens=100, keep_recent=2, summarize=lambda _m: "CUSTOM SUMMARY")
    out = await compactor.maybe_compact(_history(30))
    assert "CUSTOM SUMMARY" in out[1].content[0].text
