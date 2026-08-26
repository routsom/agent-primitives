from collections.abc import Callable

import pytest

from multiagent_boilerplate.harness.errors import ClassifiedError
from multiagent_boilerplate.providers.resilient import ResilienceOptions, ResilientChatModel
from multiagent_boilerplate.providers.types import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ProviderMessage,
    TextBlock,
    TokenUsage,
)

OK = ChatCompletionResult(
    message=ProviderMessage(role="assistant", content=[TextBlock(text="ok")]),
    usage=TokenUsage(input_tokens=1, output_tokens=1),
    stop_reason="end_turn",
)


class ScriptedModel:
    def __init__(self, provider: str, model: str, script: Callable[[int], object]) -> None:
        self.provider = provider
        self.model = model
        self.calls = 0
        self._script = script

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        outcome = self._script(self.calls)
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, ChatCompletionResult)
        return outcome


async def _no_sleep(_seconds: float) -> None:
    return None


def _opts(**kwargs: object) -> ResilienceOptions:
    base: dict = {"timeout_ms": 0, "max_retries": 2, "base_delay_ms": 1, "sleep": _no_sleep}
    base.update(kwargs)
    return ResilienceOptions(**base)  # type: ignore[arg-type]


async def test_retries_transient_then_succeeds() -> None:
    primary = ScriptedModel("p", "m", lambda call: ClassifiedError("transient", "429 slow") if call < 2 else OK)
    resilient = ResilientChatModel(primary, _opts(max_retries=2))
    result = await resilient.complete(ChatCompletionRequest(messages=[]))
    assert result.stop_reason == "end_turn"
    assert primary.calls == 3


async def test_fails_over_to_fallback_after_retries() -> None:
    primary = ScriptedModel("p", "m", lambda _call: ClassifiedError("transient", "503 down"))
    fallback = ScriptedModel("f", "m2", lambda _call: OK)
    resilient = ResilientChatModel(primary, _opts(max_retries=1, fallbacks=[fallback]))
    result = await resilient.complete(ChatCompletionRequest(messages=[]))
    assert result.stop_reason == "end_turn"
    assert primary.calls == 2
    assert fallback.calls == 1


async def test_does_not_retry_non_transient() -> None:
    primary = ScriptedModel("p", "m", lambda _call: ClassifiedError("auth", "invalid api key"))
    fallback = ScriptedModel("f", "m2", lambda _call: OK)
    resilient = ResilientChatModel(primary, _opts(max_retries=3, fallbacks=[fallback]))
    with pytest.raises(ClassifiedError):
        await resilient.complete(ChatCompletionRequest(messages=[]))
    assert primary.calls == 1
    assert fallback.calls == 0


class HangingModel:
    provider = "p"
    model = "m"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, _request: ChatCompletionRequest) -> ChatCompletionResult:
        import asyncio

        self.calls += 1
        if self.calls == 1:
            await asyncio.sleep(10)  # exceeds the 5ms timeout
        return OK


async def test_times_out_hung_call_and_retries() -> None:
    model = HangingModel()
    resilient = ResilientChatModel(model, _opts(timeout_ms=5, max_retries=1))
    result = await resilient.complete(ChatCompletionRequest(messages=[]))
    assert result.stop_reason == "end_turn"
    assert model.calls == 2


def test_proxies_primary_identity() -> None:
    primary = ScriptedModel("anthropic", "claude-sonnet-5", lambda _call: OK)
    resilient = ResilientChatModel(primary, _opts(max_retries=0))
    assert resilient.provider == "anthropic"
    assert resilient.model == "claude-sonnet-5"
