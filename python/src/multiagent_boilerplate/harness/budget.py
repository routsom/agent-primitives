"""Two circuit breakers, tracked separately (notes section 8-9): runaway spawning vs. runaway retrying."""

from __future__ import annotations


class DelegationDepthExceededError(Exception):
    def __init__(self, depth: int, cap: int) -> None:
        super().__init__(f"delegation depth {depth} exceeds cap {cap} - rejecting further spawning")


class SubagentCountExceededError(Exception):
    def __init__(self, count: int, cap: int) -> None:
        super().__init__(f"requested {count} subagents, exceeds per-call cap {cap}")


class ToolCallBudgetExceededError(Exception):
    def __init__(self, role: str, cap: int) -> None:
        super().__init__(f'role "{role}" exceeded its tool-call budget of {cap} for this task')


def assert_depth_within_cap(depth: int, cap: int) -> None:
    if depth > cap:
        raise DelegationDepthExceededError(depth, cap)


def assert_subagent_count_within_cap(count: int, cap: int) -> None:
    if count > cap:
        raise SubagentCountExceededError(count, cap)


class ToolCallBudget:
    def __init__(self, role: str, cap: int) -> None:
        self._role = role
        self._cap = cap
        self._used = 0

    def consume(self) -> None:
        self._used += 1
        if self._used > self._cap:
            raise ToolCallBudgetExceededError(self._role, self._cap)

    @property
    def remaining(self) -> int:
        return max(0, self._cap - self._used)


class RunBudgetExceededError(Exception):
    def __init__(self, consumed: int, cap: int) -> None:
        super().__init__(f"run token budget exhausted: consumed {consumed} tokens, ceiling is {cap}")


class RunBudget:
    """Session-level cost/token ceiling shared across the *entire* run - the lead agent and
    every subagent it spawns count against one budget (notes section 15). This stops a runaway
    swarm from spending unbounded tokens even when every per-agent and per-tool cap is still
    within limits. One instance per run, threaded through the whole tree. A ceiling of 0 (or
    negative) means unlimited."""

    def __init__(self, max_tokens: int) -> None:
        self._max_tokens = max_tokens
        self._consumed = 0

    def record(self, usage: object) -> None:
        self._consumed += int(getattr(usage, "input_tokens", 0)) + int(getattr(usage, "output_tokens", 0))

    def is_exhausted(self) -> bool:
        return self._max_tokens > 0 and self._consumed >= self._max_tokens

    def assert_within_ceiling(self) -> None:
        if self.is_exhausted():
            raise RunBudgetExceededError(self._consumed, self._max_tokens)

    @property
    def consumed(self) -> int:
        return self._consumed
