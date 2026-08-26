"""Least-privilege tool/role scoping (notes section 6-7)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import AuthFailure


class HarnessScopeError(AuthFailure):
    """A scope violation is an authorization failure - it classifies as `auth` (no retry,
    security-logged)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass
class AgentRoleDef:
    role: str
    allowed_tools: list[str]
    can_spawn: list[str]
    max_delegation_depth: int
    budget: dict
    prompt_file: str = ""
    description: str = ""
    model_preference: dict = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict) -> AgentRoleDef:
        return AgentRoleDef(
            role=data["role"],
            allowed_tools=data.get("allowedTools", []),
            can_spawn=data.get("canSpawn", []),
            max_delegation_depth=data.get("maxDelegationDepth", 0),
            budget=data.get("budget", {"maxToolCalls": 10}),
            prompt_file=data.get("promptFile", ""),
            description=data.get("description", ""),
            model_preference=data.get("modelPreference", {}),
        )


def assert_tool_allowed(role: AgentRoleDef, tool_name: str) -> None:
    if tool_name not in role.allowed_tools:
        raise HarnessScopeError(f'role "{role.role}" is not permitted to call tool "{tool_name}"')


def assert_can_spawn(role: AgentRoleDef, target_role: str) -> None:
    if target_role not in role.can_spawn:
        raise HarnessScopeError(f'role "{role.role}" is not permitted to spawn role "{target_role}"')
