from __future__ import annotations

from ..types import ToolContext


class SpawnSubagentsTool:
    name = "spawn_subagents"
    description = (
        "Spawn one or more subagents in parallel, each with its own isolated context, given an "
        "explicit AgentTask (objective, output format, allowed tools, boundaries, budget) per "
        "specs/schemas/agent-task.schema.json. Returns each subagent's distilled findings plus "
        "an artifact reference. Subject to the harness's subagent-count and delegation-depth caps."
    )
    input_schema = {
        "type": "object",
        "required": ["tasks"],
        "properties": {"tasks": {"type": "array", "items": {"type": "object"}}},
    }
    exposable = False

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        return await ctx.runtime.spawn_subagents(input_["tasks"], ctx.delegation_depth + 1)


spawn_subagents_tool = SpawnSubagentsTool()
