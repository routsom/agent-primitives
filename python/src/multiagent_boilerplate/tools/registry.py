from __future__ import annotations

from ..mcp_.client import McpClientManager
from .builtin.mcp_call import McpCallTool
from .builtin.read_artifact import read_artifact_tool
from .builtin.read_file import read_file_tool
from .builtin.save_plan import save_plan_tool
from .builtin.search_web import search_web_tool
from .builtin.spawn_subagents import spawn_subagents_tool
from .builtin.write_artifact import write_artifact_tool
from .types import Tool


def build_tool_registry(mcp_client: McpClientManager | None = None) -> list[Tool]:
    tools: list[Tool] = [
        spawn_subagents_tool,
        read_artifact_tool,
        write_artifact_tool,
        save_plan_tool,
        search_web_tool,
        read_file_tool,
    ]
    if mcp_client is not None:
        tools.append(McpCallTool(mcp_client))
    return tools
