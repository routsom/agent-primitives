import pytest

from multiagent_boilerplate.harness import (
    AgentRoleDef,
    DelegationDepthExceededError,
    HarnessScopeError,
    IdempotencyCache,
    RunBudget,
    RunBudgetExceededError,
    SubagentCountExceededError,
    ToolCallBudget,
    ToolCallBudgetExceededError,
    assert_depth_within_cap,
    assert_subagent_count_within_cap,
    assert_tool_allowed,
)


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def test_run_budget_trips_at_ceiling() -> None:
    budget = RunBudget(100)
    budget.record(_Usage(40, 30))
    assert budget.is_exhausted() is False
    budget.record(_Usage(20, 20))
    assert budget.is_exhausted() is True
    with pytest.raises(RunBudgetExceededError):
        budget.assert_within_ceiling()
    assert budget.consumed == 110


def test_run_budget_zero_is_unlimited() -> None:
    budget = RunBudget(0)
    budget.record(_Usage(1_000_000, 1_000_000))
    assert budget.is_exhausted() is False


def _role(allowed_tools: list[str]) -> AgentRoleDef:
    return AgentRoleDef(
        role="subagent", allowed_tools=allowed_tools, can_spawn=[], max_delegation_depth=0, budget={"maxToolCalls": 5}
    )


def test_allows_a_tool_explicitly_granted_to_the_role() -> None:
    role = _role(["search_web"])
    assert_tool_allowed(role, "search_web")  # does not raise


def test_rejects_a_tool_not_granted_to_the_role() -> None:
    role = _role(["search_web"])
    with pytest.raises(HarnessScopeError):
        assert_tool_allowed(role, "spawn_subagents")


def test_rejects_delegation_depth_beyond_the_cap() -> None:
    with pytest.raises(DelegationDepthExceededError):
        assert_depth_within_cap(3, 2)
    assert_depth_within_cap(2, 2)  # does not raise


def test_rejects_a_subagent_count_beyond_the_cap() -> None:
    with pytest.raises(SubagentCountExceededError):
        assert_subagent_count_within_cap(9, 8)
    assert_subagent_count_within_cap(8, 8)  # does not raise


def test_enforces_a_per_role_tool_call_budget() -> None:
    budget = ToolCallBudget("subagent", 2)
    budget.consume()
    budget.consume()
    with pytest.raises(ToolCallBudgetExceededError):
        budget.consume()


async def test_idempotency_cache_runs_a_key_once_for_concurrent_calls() -> None:
    import asyncio

    calls = 0
    cache = IdempotencyCache()

    async def fn() -> str:
        nonlocal calls
        calls += 1
        return "result"

    a, b = await asyncio.gather(cache.run("key-1", fn), cache.run("key-1", fn))
    assert a == "result"
    assert b == "result"
    assert calls == 1
