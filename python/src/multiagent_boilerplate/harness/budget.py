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
