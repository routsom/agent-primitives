"""Repeated calls with the same idempotency key resolve to the single first result
(specs/schemas/tool-envelope.schema.json)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class IdempotencyCache:
    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Task] = {}

    async def run(self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        existing = self._in_flight.get(key)
        if existing is not None:
            return await existing

        task = asyncio.ensure_future(fn())
        self._in_flight[key] = task
        try:
            return await task
        except Exception:
            self._in_flight.pop(key, None)
            raise
