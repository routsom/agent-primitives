from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ToolRuntime(Protocol):
    """Narrow surface tools need back into the runtime, avoiding a circular full-runtime import."""

    async def spawn_subagents(self, tasks: list[dict], depth: int) -> Any: ...
    async def write_artifact(self, kind: str, summary: str, content: Any, created_by: str) -> Any: ...
    async def read_artifact(self, artifact_id: str) -> Any: ...
    async def save_plan(self, plan: Any) -> None: ...


@dataclass
class ToolContext:
    agent_role: str
    delegation_depth: int
    runtime: ToolRuntime


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict
    exposable: bool

    async def execute(self, input_: dict, ctx: ToolContext) -> Any: ...
