"""Shared infrastructure every agent's tool call routes through - no agent-to-agent shortcut
around it (notes section 7). Validates scope, applies idempotency, and executes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..tools.types import Tool, ToolContext, ToolRuntime
from .budget import (
    DelegationDepthExceededError,
    SubagentCountExceededError,
    ToolCallBudget,
    ToolCallBudgetExceededError,
    assert_depth_within_cap,
    assert_subagent_count_within_cap,
)
from .idempotency import IdempotencyCache
from .schemas import load_agent_role, load_prompt, load_schema
from .scope import AgentRoleDef, HarnessScopeError, assert_can_spawn, assert_tool_allowed
from .validate import validate_agent_task, validate_artifact_ref, validate_trace_span

__all__ = [
    "Harness",
    "HarnessToolCall",
    "AgentRoleDef",
    "HarnessScopeError",
    "assert_tool_allowed",
    "assert_can_spawn",
    "DelegationDepthExceededError",
    "SubagentCountExceededError",
    "ToolCallBudget",
    "ToolCallBudgetExceededError",
    "assert_depth_within_cap",
    "assert_subagent_count_within_cap",
    "IdempotencyCache",
    "load_agent_role",
    "load_prompt",
    "load_schema",
    "validate_agent_task",
    "validate_artifact_ref",
    "validate_trace_span",
]


@dataclass
class HarnessToolCall:
    idempotency_key: str
    tool_name: str
    input: dict[str, Any]
    delegation_depth: int


class Harness:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}
        self._idempotency = IdempotencyCache()

    async def execute(self, role: AgentRoleDef, call: HarnessToolCall, runtime: ToolRuntime) -> Any:
        assert_tool_allowed(role, call.tool_name)
        tool = self._tools.get(call.tool_name)
        if tool is None:
            raise ValueError(f'harness: unknown tool "{call.tool_name}"')

        async def run() -> Any:
            ctx = ToolContext(agent_role=role.role, delegation_depth=call.delegation_depth, runtime=runtime)
            return await tool.execute(call.input, ctx)

        return await self._idempotency.run(call.idempotency_key, run)

    def tool_definitions(self, role: AgentRoleDef) -> list[dict]:
        defs = []
        for name in role.allowed_tools:
            tool = self._tools.get(name)
            if tool is not None:
                defs.append({"name": tool.name, "description": tool.description, "input_schema": tool.input_schema})
        return defs
