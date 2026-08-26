"""Sliding-window rate limiter (notes section 19: 'rate limiting at every layer'). Reject
abusive or runaway traffic at the earliest possible point - before the model ever runs -
because the cost of rejecting early is near zero while the cost of processing then rejecting is
a full model call. Keyed by caller identity (auth token, or remote address as a fallback).

In-memory by design for the boilerplate: a single process. For multi-instance deployments,
back the same interface with a shared store (Redis) - see docs/extending.md.
"""

from __future__ import annotations

import time


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_ms: int) -> None:
        self._max_requests = max_requests
        self._window_ms = window_ms
        self._hits: dict[str, list[float]] = {}

    def try_acquire(self, key: str, now: float | None = None) -> bool:
        """Returns True if the request is allowed (and records it); False if the caller is over
        the limit."""
        now = now if now is not None else time.monotonic() * 1000.0
        cutoff = now - self._window_ms
        recent = [t for t in self._hits.get(key, []) if t > cutoff]
        if len(recent) >= self._max_requests:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True
