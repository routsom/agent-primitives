"""Thin adapter over the official Anthropic SDK. No routing library, no framework."""

from __future__ import annotations

import json

from anthropic import AsyncAnthropic

from .types import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ContentBlock,
    ProviderMessage,
    TextBlock,
    TokenUsage,
    ToolCallBlock,
    ToolResultBlock,
)


class AnthropicChatModel:
    provider = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        self.model = model
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=request.max_tokens,
            system=request.system if request.system else None,
            messages=[_to_anthropic_message(m) for m in request.messages],
            tools=[
                {"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in request.tools
            ]
            or None,
        )

        return ChatCompletionResult(
            message=_from_anthropic_message(response),
            usage=TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cached_input_tokens=getattr(response.usage, "cache_read_input_tokens", None),
            ),
            stop_reason="tool_use"
            if response.stop_reason == "tool_use"
            else "max_tokens"
            if response.stop_reason == "max_tokens"
            else "end_turn",
        )


def _to_anthropic_message(message: ProviderMessage) -> dict:
    content = []
    for block in message.content:
        if isinstance(block, TextBlock):
            content.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolCallBlock):
            content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        elif isinstance(block, ToolResultBlock):
            content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.tool_call_id,
                    "content": block.output if isinstance(block.output, str) else json.dumps(block.output),
                    "is_error": block.is_error,
                }
            )
    return {"role": "assistant" if message.role == "assistant" else "user", "content": content}


def _from_anthropic_message(response) -> ProviderMessage:
    content: list[ContentBlock] = []
    for block in response.content:
        if block.type == "text":
            content.append(TextBlock(text=block.text))
        elif block.type == "tool_use":
            content.append(ToolCallBlock(id=block.id, name=block.name, input=block.input))
    return ProviderMessage(role="assistant", content=content)
