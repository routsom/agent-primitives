from __future__ import annotations

from ..types import ToolContext


class SavePlanTool:
    name = "save_plan"
    description = (
        "Persist the current plan to durable memory before spawning subagents, so a context "
        "truncation mid-run doesn't lose the strategy."
    )
    input_schema = {"type": "object", "required": ["plan"], "properties": {"plan": {}}}
    exposable = False

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        await ctx.runtime.save_plan(input_["plan"])
        return {"saved": True}


save_plan_tool = SavePlanTool()
