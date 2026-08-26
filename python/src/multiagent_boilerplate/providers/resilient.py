"""Infrastructure-level resilience for the model dependency (notes section 15: 'a 429/529
means the model never ran at all... needs its own handling: retry with backoff, and ideally a
configured fallback to another model/region').

Wraps a primary ChatModel and, transparently: times out a hung call (classified transient),
retries transient failures on the same model with exponential backoff, fails over to the next
configured fallback when retries are exhausted, and re-raises non-transient errors
(validation/auth/permanent) immediately. It is itself a ChatModel, so nothing above the
provider layer knows resilience is happening - it's a decorator, not a new abstraction.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from ..harness.errors import ClassifiedError, classify_error
from .types import ChatCompletionRequest, ChatCompletionResult, ChatModel


@dataclass
class ResilienceOptions:
    timeout_ms: int
    max_retries: int
    base_delay_ms: int
    fallbacks: list[ChatModel] = field(default_factory=list)
    # Injectable sleep, so tests don't wait on real backoff.
    sleep: Callable[[float], Awaitable[None]] | None = None


class ResilientChatModel:
    def __init__(self, primary: ChatModel, options: ResilienceOptions) -> None:
        self._primary = primary
        self._options = options
        self._chain: list[ChatModel] = [primary, *options.fallbacks]
        self._sleep = options.sleep or asyncio.sleep

    @property
    def provider(self) -> str:
        return self._primary.provider

    @property
    def model(self) -> str:
        return self._primary.model

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        last_error: Exception | None = None

        for model in self._chain:
            for attempt in range(self._options.max_retries + 1):
                try:
                    return await self._with_timeout(model.complete(request))
                except Exception as error:  # noqa: BLE001 - classified below, re-raised if not transient
                    last_error = error
                    classified = classify_error(error)
                    # Only transient errors are worth retrying or failing over. Everything else
                    # (bad request, auth, not-found) fails identically, so surface it immediately.
                    if classified.type != "transient":
                        raise
                    if attempt < self._options.max_retries:
                        await self._sleep(self._backoff(attempt))
            # Retries on this model exhausted - fall through to the next fallback in the chain.

        assert last_error is not None
        raise last_error

    def _backoff(self, attempt: int) -> float:
        base = self._options.base_delay_ms * (2**attempt)
        jitter = random.random() * self._options.base_delay_ms
        return (base + jitter) / 1000.0

    async def _with_timeout(self, awaitable: Awaitable[ChatCompletionResult]) -> ChatCompletionResult:
        if self._options.timeout_ms <= 0:
            return await awaitable
        try:
            return await asyncio.wait_for(awaitable, timeout=self._options.timeout_ms / 1000.0)
        except TimeoutError as error:
            raise ClassifiedError("transient", f"model call timed out after {self._options.timeout_ms}ms") from error
