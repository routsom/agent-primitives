"""Published at /.well-known/agent.json - generated from specs/agents/, so it can never
overstate what the agent will do (specs/protocols/a2a.md)."""

from __future__ import annotations

from ..harness.schemas import load_agent_role


def build_agent_card(role_name: str, base_url: str) -> dict:
    role = load_agent_role(role_name)
    return {
        "name": f"agent-primitives:{role['role']}",
        "role": role["role"],
        "description": role["description"],
        "capabilities": {"allowedTools": role["allowedTools"], "maxToolCalls": role["budget"]["maxToolCalls"]},
        "url": base_url,
    }
