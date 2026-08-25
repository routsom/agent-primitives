from __future__ import annotations

from ..types import ToolContext


class ReadArtifactTool:
    name = "read_artifact"
    description = "Fetch the full content of a previously stored artifact by id, when a distilled summary isn't enough."
    input_schema = {"type": "object", "required": ["artifactId"], "properties": {"artifactId": {"type": "string"}}}
    exposable = False

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        return await ctx.runtime.read_artifact(input_["artifactId"])


read_artifact_tool = ReadArtifactTool()
