"""Exposes this system's own exposable tools (specs/protocols/mcp.md) as an MCP server, so
other MCP-compatible clients - including another instance of this boilerplate - can call
them. Only tools with `exposable = True` are surfaced."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..tools.types import Tool, ToolContext, ToolRuntime


class _UnavailableRuntime:
    async def spawn_subagents(self, tasks, depth):
        raise RuntimeError("spawn_subagents is not exposed over MCP")

    async def write_artifact(self, kind, summary, content, created_by):
        raise RuntimeError("write_artifact is not exposed over MCP")

    async def read_artifact(self, artifact_id):
        raise RuntimeError("read_artifact is not exposed over MCP")

    async def save_plan(self, plan):
        raise RuntimeError("save_plan is not exposed over MCP")


def create_mcp_server(tools: list[Tool]) -> MCPServer:
    server = MCPServer("agent-primitives")
    runtime: ToolRuntime = _UnavailableRuntime()

    for tool in tools:
        if not tool.exposable:
            continue

        def make_handler(bound_tool: Tool):
            async def handler(**kwargs: object) -> object:
                ctx = ToolContext(agent_role="mcp-external", delegation_depth=0, runtime=runtime)
                return await bound_tool.execute(kwargs, ctx)

            handler.__name__ = bound_tool.name
            handler.__doc__ = bound_tool.description
            return handler

        server.add_tool(make_handler(tool), name=tool.name, description=tool.description)

    return server


def run_mcp_server(tools: list[Tool]) -> None:
    server = create_mcp_server(tools)
    server.run(transport="stdio")
