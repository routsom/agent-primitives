"""Deterministic replay (VCR): record once, replay offline with zero base-model calls."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from multiagent_boilerplate.providers.replay import ReplayChatModel
from multiagent_boilerplate.providers.types import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ProviderMessage,
    TextBlock,
    TokenUsage,
)


class CountingModel:
    """A base model that counts how many times it was actually called."""

    provider = "mock"
    model = "counting-1"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        self.calls += 1
        return ChatCompletionResult(
            message=ProviderMessage(role="assistant", content=[TextBlock(text=f"answer #{self.calls}")]),
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            stop_reason="end_turn",
        )


def _req(text: str) -> ChatCompletionRequest:
    return ChatCompletionRequest(system="s", messages=[ProviderMessage(role="user", content=[TextBlock(text=text)])])


@pytest.fixture
def cassette() -> Path:
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "cassette.json"


async def test_records_then_replays_without_calling_base(cassette: Path) -> None:
    base = CountingModel()
    recorded = await ReplayChatModel(base, cassette).complete(_req("hello"))
    assert base.calls == 1

    # A fresh decorator over a fresh base loads the cassette from disk: same answer, zero calls.
    base2 = CountingModel()
    replayed = await ReplayChatModel(base2, cassette).complete(_req("hello"))
    assert base2.calls == 0
    assert replayed.message.content[0].text == recorded.message.content[0].text


async def test_distinguishes_requests_by_hash(cassette: Path) -> None:
    base = CountingModel()
    vcr = ReplayChatModel(base, cassette)
    a = await vcr.complete(_req("query A"))
    b = await vcr.complete(_req("query B"))
    assert base.calls == 2
    assert a.message.content[0].text != b.message.content[0].text
    # Replaying A returns A's recording, not B's, and does not call the base again.
    again = await vcr.complete(_req("query A"))
    assert again.message.content[0].text == a.message.content[0].text
    assert base.calls == 2


async def test_replay_only_mode_raises_on_miss(cassette: Path) -> None:
    vcr = ReplayChatModel(CountingModel(), cassette, mode="replay")
    with pytest.raises(Exception, match="no cassette entry"):
        await vcr.complete(_req("never recorded"))
