"""Thin adapter over the official Google GenAI SDK."""

from __future__ import annotations

from google import genai
from google.genai import types as genai_types

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


class GeminiChatModel:
    provider = "google"

    def __init__(self, api_key: str, model: str = "gemini-3-pro") -> None:
        self.model = model
        self._client = genai.Client(api_key=api_key)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        config = genai_types.GenerateContentConfig(
            system_instruction=request.system,
            max_output_tokens=request.max_tokens,
            tools=(
                [genai_types.Tool(function_declarations=[_to_function_declaration(t) for t in request.tools])]
                if request.tools
                else None
            ),
        )

        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=[_to_gemini_content(m) for m in request.messages],
            config=config,
        )

        content: list[ContentBlock] = []
        call_index = 0
        parts = response.candidates[0].content.parts if response.candidates and response.candidates[0].content else []
        for part in parts:
            if part.text:
                content.append(TextBlock(text=part.text))
            if part.function_call:
                content.append(
                    ToolCallBlock(
                        id=f"{part.function_call.name}-{call_index}",
                        name=part.function_call.name or "unknown",
                        input=dict(part.function_call.args or {}),
                    )
                )
                call_index += 1

        has_tool_call = any(isinstance(b, ToolCallBlock) for b in content)
        usage = response.usage_metadata
        return ChatCompletionResult(
            message=ProviderMessage(role="assistant", content=content),
            usage=TokenUsage(
                input_tokens=usage.prompt_token_count if usage else 0,
                output_tokens=usage.candidates_token_count if usage else 0,
            ),
            stop_reason="tool_use" if has_tool_call else "end_turn",
        )


def _to_function_declaration(tool) -> genai_types.FunctionDeclaration:
    return genai_types.FunctionDeclaration(name=tool.name, description=tool.description, parameters=tool.input_schema)


def _to_gemini_content(message: ProviderMessage) -> genai_types.Content:
    parts = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(genai_types.Part(text=block.text))
        elif isinstance(block, ToolCallBlock):
            parts.append(genai_types.Part(function_call=genai_types.FunctionCall(name=block.name, args=block.input)))
        elif isinstance(block, ToolResultBlock):
            response = block.output if isinstance(block.output, dict) else {"value": block.output}
            parts.append(
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(name=block.tool_call_id, response=response)
                )
            )
    return genai_types.Content(role="model" if message.role == "assistant" else "user", parts=parts)
