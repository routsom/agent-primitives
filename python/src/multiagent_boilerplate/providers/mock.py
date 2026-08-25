"""Deterministic, network-free provider - the Python mirror of providers/mock.ts.

Used as the default so `uv sync && uv run python -m examples.research_task` works with zero
API keys, and so CI never depends on a live model. Behavior is a small state machine keyed on
(a) which role's prompt is in `system` and (b) how many assistant turns have already happened
in *this* agent's own message history - each agent gets an isolated context, so counting prior
assistant turns is an accurate, pure-function way to track progress.
"""

from __future__ import annotations

import json
import re

from .types import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ContentBlock,
    ProviderMessage,
    TextBlock,
    TokenUsage,
    ToolCallBlock,
    ToolResultBlock,
    text_of,
)


class MockChatModel:
    provider = "mock"
    model = "mock-deterministic-1"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        turn = sum(1 for m in request.messages if m.role == "assistant")
        system = request.system or ""
        first_user = next((m for m in request.messages if m.role == "user"), None)
        first_user_text = text_of(first_user) if first_user else ""

        if "You are the lead agent" in system:
            return _lead_turn(turn, first_user_text, request)
        if "You are a subagent" in system:
            return _subagent_turn(turn, request)
        if "You are the citation and synthesis agent" in system:
            return _citation_turn(first_user_text)
        if "You are evaluating the output" in system:
            return _judge_turn()

        return ChatCompletionResult(
            message=ProviderMessage(
                role="assistant", content=[TextBlock(text=f"[mock] Direct answer to: {first_user_text}")]
            ),
            usage=TokenUsage(input_tokens=_estimate_tokens(request), output_tokens=40),
            stop_reason="end_turn",
        )


def _lead_turn(turn: int, topic: str, request: ChatCompletionRequest) -> ChatCompletionResult:
    can_spawn = any(t.name == "spawn_subagents" for t in request.tools)

    if turn == 0 and can_spawn:
        tasks = [
            {
                "taskId": "sub-1",
                "role": "subagent",
                "objective": f"Investigate angle A of: {topic}",
                "outputFormat": "bullet list of findings with source references",
                "allowedTools": ["search_web", "write_artifact"],
                "boundaries": "Cover angle A only; do not duplicate angle B's territory.",
                "budget": {"maxToolCalls": 15, "maxDelegationDepth": 0},
            },
            {
                "taskId": "sub-2",
                "role": "subagent",
                "objective": f"Investigate angle B of: {topic}",
                "outputFormat": "bullet list of findings with source references",
                "allowedTools": ["search_web", "write_artifact"],
                "boundaries": "Cover angle B only; do not duplicate angle A's territory.",
                "budget": {"maxToolCalls": 15, "maxDelegationDepth": 0},
            },
        ]
        return _tool_call_result("call-spawn-0", "spawn_subagents", {"tasks": tasks}, request)

    last_result = _find_last_tool_result(request.messages)
    findings_text = json.dumps(last_result.output) if last_result else "(no findings)"
    answer = f'[mock] Based on subagent findings, here is the synthesized answer for "{topic}": {findings_text}'
    return ChatCompletionResult(
        message=ProviderMessage(role="assistant", content=[TextBlock(text=answer)]),
        usage=TokenUsage(input_tokens=_estimate_tokens(request), output_tokens=80),
        stop_reason="end_turn",
    )


def _subagent_turn(turn: int, request: ChatCompletionRequest) -> ChatCompletionResult:
    objective = _task_objective(request)
    if turn == 0:
        return _tool_call_result("call-search-0", "search_web", {"query": objective}, request)
    if turn == 1:
        last_result = _find_last_tool_result(request.messages)
        return _tool_call_result(
            "call-artifact-0",
            "write_artifact",
            {
                "kind": "raw-findings",
                "summary": f"Findings for: {objective}",
                "content": last_result.output if last_result else {},
            },
            request,
        )
    last_result = _find_last_tool_result(request.messages)
    output = json.dumps(last_result.output) if last_result else "{}"
    return ChatCompletionResult(
        message=ProviderMessage(
            role="assistant",
            content=[TextBlock(text=f'[mock] Distilled findings for "{objective}": mock result available at {output}')],
        ),
        usage=TokenUsage(input_tokens=_estimate_tokens(request), output_tokens=60),
        stop_reason="end_turn",
    )


def _citation_turn(input_text: str) -> ChatCompletionResult:
    return ChatCompletionResult(
        message=ProviderMessage(role="assistant", content=[TextBlock(text=f"[mock] Cited synthesis: {input_text}")]),
        usage=TokenUsage(input_tokens=len(input_text), output_tokens=60),
        stop_reason="end_turn",
    )


def _judge_turn() -> ChatCompletionResult:
    scores = {"accuracy": 4, "completeness": 4, "source_quality": 3, "process": 4, "disclosure": 5}
    payload = {
        "scores": scores,
        "justifications": {k: "mock justification" for k in scores},
        "flag_for_human_review": False,
    }
    return ChatCompletionResult(
        message=ProviderMessage(role="assistant", content=[TextBlock(text=json.dumps(payload))]),
        usage=TokenUsage(input_tokens=100, output_tokens=60),
        stop_reason="end_turn",
    )


def _tool_call_result(call_id: str, name: str, input_: dict, request: ChatCompletionRequest) -> ChatCompletionResult:
    content: list[ContentBlock] = [ToolCallBlock(id=call_id, name=name, input=input_)]
    return ChatCompletionResult(
        message=ProviderMessage(role="assistant", content=content),
        usage=TokenUsage(input_tokens=_estimate_tokens(request), output_tokens=30),
        stop_reason="tool_use",
    )


def _find_last_tool_result(messages: list[ProviderMessage]) -> ToolResultBlock | None:
    for message in reversed(messages):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                return block
    return None


def _task_objective(request: ChatCompletionRequest) -> str:
    system = request.system or ""
    match = re.search(r"Objective: (.+)", system)
    if match:
        return match.group(1)
    first_user = next((m for m in request.messages if m.role == "user"), None)
    return text_of(first_user) if first_user else ""


def _estimate_tokens(request: ChatCompletionRequest) -> int:
    approx = sum(len(text_of(m)) + 20 for m in request.messages)
    return max(1, approx // 4)
