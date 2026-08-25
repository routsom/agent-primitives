"""The generic agent loop every role (lead, subagent, citation, judge) runs through. Not
role-specific logic - that lives entirely in specs/prompts and specs/agents. This function is
the harness-enforced tool-use loop: call model, execute any requested tool calls through the
harness, feed results back, repeat until the model stops requesting tools."""

from __future__ import annotations

from dataclasses import dataclass

from ..harness import AgentRoleDef, Harness, HarnessToolCall, ToolCallBudget, load_agent_role, load_prompt
from ..providers.types import (
    ChatCompletionRequest,
    ChatModel,
    ProviderMessage,
    TextBlock,
    ToolCallBlock,
    ToolDefinition,
    ToolResultBlock,
    text_of,
)
from ..tools.types import ToolRuntime
from ..tracing.tracer import Tracer
from .types import AgentResult


@dataclass
class RunAgentParams:
    role_name: str
    user_prompt: str
    model: ChatModel
    harness: Harness
    runtime: ToolRuntime
    tracer: Tracer
    task_id: str
    delegation_depth: int
    parent_span_id: str | None = None
    extra_system_context: str | None = None
    max_turns: int | None = None


async def run_agent(params: RunAgentParams) -> AgentResult:
    role_data = load_agent_role(params.role_name)
    role = AgentRoleDef.from_dict(role_data)
    system_prompt = load_prompt(role.prompt_file)
    if params.extra_system_context:
        system_prompt = f"{system_prompt}\n\n---\n\n{params.extra_system_context}"

    budget = ToolCallBudget(role.role, role.budget["maxToolCalls"])
    max_turns = params.max_turns if params.max_turns is not None else role.budget["maxToolCalls"] + 2

    messages: list[ProviderMessage] = [ProviderMessage(role="user", content=[TextBlock(text=params.user_prompt)])]
    artifact_refs: list[dict] = []

    agent_span = params.tracer.start_span(
        "agent",
        f"{role.role}:{params.task_id}",
        parent_span_id=params.parent_span_id,
        agent_role=role.role,
        delegation_depth=params.delegation_depth,
    )

    tool_defs = [
        ToolDefinition(name=d["name"], description=d["description"], input_schema=d["input_schema"])
        for d in params.harness.tool_definitions(role)
    ]

    for turn in range(max_turns):
        model_span = params.tracer.start_span(
            "model_call",
            f"{role.role} turn {turn}",
            parent_span_id=agent_span.span_id,
            agent_role=role.role,
            delegation_depth=params.delegation_depth,
        )

        result = await params.model.complete(
            ChatCompletionRequest(system=system_prompt, messages=messages, tools=tool_defs)
        )
        params.tracer.end_span(
            model_span,
            "ok",
            token_usage={"inputTokens": result.usage.input_tokens, "outputTokens": result.usage.output_tokens},
        )
        messages.append(result.message)

        if result.stop_reason != "tool_use":
            params.tracer.end_span(agent_span, "ok")
            return AgentResult(
                task_id=params.task_id,
                role=role.role,
                text=text_of(result.message),
                artifact_refs=artifact_refs,
                status="ok",
            )

        tool_calls = [b for b in result.message.content if isinstance(b, ToolCallBlock)]
        tool_results: list[ToolResultBlock] = []

        for call in tool_calls:
            tool_span = params.tracer.start_span(
                "tool_call",
                call.name,
                parent_span_id=agent_span.span_id,
                agent_role=role.role,
                delegation_depth=params.delegation_depth,
            )
            try:
                budget.consume()
                output = await params.harness.execute(
                    role,
                    HarnessToolCall(
                        idempotency_key=call.id,
                        tool_name=call.name,
                        input=call.input,
                        delegation_depth=params.delegation_depth,
                    ),
                    params.runtime,
                )
                params.tracer.end_span(tool_span, "ok")
                if call.name == "write_artifact":
                    artifact_refs.append(output)
                tool_results.append(ToolResultBlock(tool_call_id=call.id, output=output))
            except Exception as error:  # noqa: BLE001 - fed back to the model, not swallowed
                params.tracer.end_span(tool_span, "error", attributes={"error": str(error)})
                tool_results.append(
                    ToolResultBlock(tool_call_id=call.id, output={"message": str(error)}, is_error=True)
                )

        messages.append(ProviderMessage(role="tool", content=list(tool_results)))

    params.tracer.end_span(agent_span, "partial")
    return AgentResult(
        task_id=params.task_id,
        role=role.role,
        text="(stopped: exceeded max turns before reaching a final answer)",
        artifact_refs=artifact_refs,
        status="partial",
    )
