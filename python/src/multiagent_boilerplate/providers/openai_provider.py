"""Thin adapter over the official OpenAI SDK, normalized to the same ChatModel contract."""

from __future__ import annotations

import json

from openai import AsyncOpenAI

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


class OpenAIChatModel:
    provider = "openai"

    def __init__(self, api_key: str, model: str = "gpt-5") -> None:
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for m in request.messages:
            messages.extend(_to_openai_messages(m))

        tools = [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
            }
            for t in request.tools
        ] or None

        response = await self._client.chat.completions.create(
            model=self.model, max_tokens=request.max_tokens, messages=messages, tools=tools
        )
        choice = response.choices[0]

        return ChatCompletionResult(
            message=_from_openai_message(choice.message),
            usage=TokenUsage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            ),
            stop_reason="tool_use"
            if choice.finish_reason == "tool_calls"
            else "max_tokens"
            if choice.finish_reason == "length"
            else "end_turn",
        )


def _to_openai_messages(message: ProviderMessage) -> list[dict]:
    text = "".join(b.text for b in message.content if isinstance(b, TextBlock))
    tool_calls = [b for b in message.content if isinstance(b, ToolCallBlock)]
    tool_results = [b for b in message.content if isinstance(b, ToolResultBlock)]

    out: list[dict] = []
    if message.role == "assistant":
        entry: dict = {"role": "assistant", "content": text or None}
        if tool_calls:
            entry["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.input)}}
                for tc in tool_calls
            ]
        out.append(entry)
    elif tool_results:
        for tr in tool_results:
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": tr.tool_call_id,
                    "content": tr.output if isinstance(tr.output, str) else json.dumps(tr.output),
                }
            )
    else:
        out.append({"role": "user", "content": text})
    return out


def _from_openai_message(message) -> ProviderMessage:
    content: list[ContentBlock] = []
    if message.content:
        content.append(TextBlock(text=message.content))
    for tc in message.tool_calls or []:
        if tc.type != "function":
            continue
        content.append(ToolCallBlock(id=tc.id, name=tc.function.name, input=json.loads(tc.function.arguments or "{}")))
    return ProviderMessage(role="assistant", content=content)
