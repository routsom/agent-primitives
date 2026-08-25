"""Normalized message/content shapes. Mirrors specs/schemas/provider-message.schema.json."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass
class TextBlock:
    text: str
    type: Literal["text"] = "text"


@dataclass
class ToolCallBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: Literal["tool_call"] = "tool_call"


@dataclass
class ToolResultBlock:
    tool_call_id: str
    output: Any
    is_error: bool = False
    type: Literal["tool_result"] = "tool_result"


ContentBlock = TextBlock | ToolCallBlock | ToolResultBlock


@dataclass
class ProviderMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: list[ContentBlock]
    name: str | None = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int | None = None


@dataclass
class ChatCompletionRequest:
    messages: list[ProviderMessage]
    system: str | None = None
    tools: list[ToolDefinition] = field(default_factory=list)
    max_tokens: int = 4096


@dataclass
class ChatCompletionResult:
    message: ProviderMessage
    usage: TokenUsage
    stop_reason: Literal["end_turn", "tool_use", "max_tokens"]


@runtime_checkable
class ChatModel(Protocol):
    """One adapter per vendor SDK. No routing library in between - this is the whole abstraction."""

    provider: str
    model: str

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult: ...


def text_of(message: ProviderMessage) -> str:
    return "\n".join(block.text for block in message.content if isinstance(block, TextBlock))
