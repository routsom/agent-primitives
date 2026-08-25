from __future__ import annotations

from ...mcp_.client import McpClientManager
from ..types import ToolContext


class McpCallTool:
    name = "mcp_call"
    description = (
        "Call a tool exposed by a connected external MCP server (config/mcp_servers.json), by server name and tool."
    )
    input_schema = {
        "type": "object",
        "required": ["server", "tool", "input"],
        "properties": {"server": {"type": "string"}, "tool": {"type": "string"}, "input": {"type": "object"}},
    }
    exposable = False

    def __init__(self, manager: McpClientManager) -> None:
        self._manager = manager

    async def execute(self, input_: dict, ctx: ToolContext) -> object:
        return await self._manager.call_tool(input_["server"], input_["tool"], input_["input"])
