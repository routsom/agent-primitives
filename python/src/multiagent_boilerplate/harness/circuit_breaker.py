"""Per-tool, system-wide circuit breaker (notes section 12: 'a circuit breaker per tool,
system-wide - not per conversation'). If a tool's failure rate spikes across all sessions, the
harness marks it unavailable and short-circuits future calls immediately, instead of every
concurrent conversation independently timing out on the same broken backend.

Distinct from the per-subagent retry cap (which bounds one agent's retries of one call) and
from provider resilience (which handles the *model* being down). This handles a *tool's
backend* being down.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CircuitBreakerOptions:
    failure_threshold: int = 5
    window_ms: int = 60_000
    cooldown_ms: int = 30_000


class ToolCircuitBreaker:
    def __init__(self, options: CircuitBreakerOptions | None = None) -> None:
        self._options = options or CircuitBreakerOptions()
        self._failures: dict[str, list[float]] = {}
        self._opened_at: dict[str, float] = {}

    def _now(self) -> float:
        return time.monotonic() * 1000.0

    def is_open(self, tool_name: str, now: float | None = None) -> bool:
        now = now if now is not None else self._now()
        opened = self._opened_at.get(tool_name)
        if opened is None:
            return False
        if now - opened >= self._options.cooldown_ms:
            # Cooldown elapsed: half-open - clear state and allow a trial call through.
            self._opened_at.pop(tool_name, None)
            self._failures.pop(tool_name, None)
            return False
        return True

    def record_success(self, tool_name: str) -> None:
        self._opened_at.pop(tool_name, None)
        self._failures.pop(tool_name, None)

    def record_failure(self, tool_name: str, now: float | None = None) -> None:
        now = now if now is not None else self._now()
        recent = [t for t in self._failures.get(tool_name, []) if t > now - self._options.window_ms]
        recent.append(now)
        self._failures[tool_name] = recent
        if len(recent) >= self._options.failure_threshold:
            self._opened_at[tool_name] = now
