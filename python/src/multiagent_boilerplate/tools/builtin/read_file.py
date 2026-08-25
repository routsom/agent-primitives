from __future__ import annotations

from pathlib import Path

from ..types import ToolContext

WORKSPACE_ROOT = Path.cwd().resolve()


class ReadFileTool:
    name = "read_file"
    description = "Read a UTF-8 text file by path, relative to the project working directory."
    input_schema = {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}
    exposable = False

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        target = Path(input_["path"])
        target = target if target.is_absolute() else (WORKSPACE_ROOT / target)
        target = target.resolve()
        if not str(target).startswith(str(WORKSPACE_ROOT)):
            raise ValueError(f"read_file: path escapes workspace root: {input_['path']}")
        return {"content": target.read_text(encoding="utf-8")}


read_file_tool = ReadFileTool()
