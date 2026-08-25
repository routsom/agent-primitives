"""Stub search tool: deterministic, offline, no external dependency. Swap `execute` for a
real provider (Brave Search, Tavily, etc.) - the contract (input/output shape, tool name) is
what agents and the mock provider are written against, so a real implementation is a drop-in
replacement."""

from __future__ import annotations

from ..types import ToolContext


class SearchWebTool:
    name = "search_web"
    description = (
        "Search the web for information relevant to `query`. Returns a short list of results "
        "with title, url, and snippet. This boilerplate ships a deterministic stub - replace "
        "with a real search API for production use."
    )
    input_schema = {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}}
    exposable = True

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        query = input_["query"]
        return {
            "results": [
                {
                    "title": f"Stub result for: {query}",
                    "url": "https://example.com/stub-result",
                    "snippet": f'Placeholder result for "{query}". Replace tools/builtin/search_web with a real API.',
                }
            ]
        }


search_web_tool = SearchWebTool()
