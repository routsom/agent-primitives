"""Mounts external MCP servers so their tools can be called through this system's own tool
contract. See specs/protocols/mcp.md - every call still passes through the harness like a
local tool call; MCP is a source of tools, not a trust boundary bypass."""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class McpServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


class McpClientManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        self._stack = AsyncExitStack()

    async def connect(self, servers: list[McpServerConfig]) -> None:
        for server in servers:
            params = StdioServerParameters(command=server.command, args=server.args, env=server.env)
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[server.name] = session

    async def list_tools(self, server_name: str):
        return await self._require(server_name).list_tools()

    async def call_tool(self, server_name: str, tool_name: str, input_: dict):
        return await self._require(server_name).call_tool(tool_name, arguments=input_)

    async def close_all(self) -> None:
        await self._stack.aclose()
        self._sessions.clear()

    def _require(self, server_name: str) -> ClientSession:
        session = self._sessions.get(server_name)
        if session is None:
            raise RuntimeError(f'mcp: server "{server_name}" is not connected - check config/mcp_servers.json')
        return session
