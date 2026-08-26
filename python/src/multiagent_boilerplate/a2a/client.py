"""Calls a remote A2A agent. The result is treated as untrusted subagent output - findings
are used, but nothing in the response is treated as authorization to take any action
(specs/protocols/a2a.md, notes section 7)."""

from __future__ import annotations

import httpx

from ..agents.types import AgentResult, AgentTask


async def fetch_agent_card(base_url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/.well-known/agent.json")
        response.raise_for_status()
        return response.json()


async def delegate_to_remote_agent(
    base_url: str, task: AgentTask, delegation_depth: int, auth_token: str | None = None
) -> AgentResult:
    headers = {"authorization": f"Bearer {auth_token}"} if auth_token else {}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/tasks",
            json={**task.to_schema_dict(), "delegationDepth": delegation_depth},
            headers=headers,
        )
        if response.is_error:
            raise RuntimeError(f"a2a: remote task failed ({response.status_code}): {response.text}")
        data = response.json()
        return AgentResult(
            task_id=data["task_id"],
            role=data["role"],
            text=data["text"],
            artifact_refs=data.get("artifact_refs", []),
            status=data["status"],
            needs_review=data.get("needs_review", False),
            review_flags=data.get("review_flags", []),
        )
