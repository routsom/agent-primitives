from __future__ import annotations

from ..types import ToolContext


class WriteArtifactTool:
    name = "write_artifact"
    description = (
        "Store a large output (raw findings, a report, code, generated data) in the artifact "
        "store and return a lightweight reference. Use this instead of returning large content inline."
    )
    input_schema = {
        "type": "object",
        "required": ["kind", "summary", "content"],
        "properties": {
            "kind": {"type": "string", "enum": ["raw-findings", "report", "code", "generated-data", "trace-export"]},
            "summary": {"type": "string"},
            "content": {},
        },
    }
    exposable = False

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        return await ctx.runtime.write_artifact(
            kind=input_["kind"], summary=input_["summary"], content=input_["content"], created_by=ctx.agent_role
        )


write_artifact_tool = WriteArtifactTool()
