"""The generic agent loop every role (lead, subagent, citation, judge) runs through. Not
role-specific logic - that lives entirely in specs/prompts and specs/agents. This function is
the harness-enforced tool-use loop: call model, execute any requested tool calls through the
harness, feed results back, repeat until the model stops requesting tools."""

from __future__ import annotations

from dataclasses import dataclass

from ..cost.pricing import compute_cost_usd
from ..harness import (
    AgentRoleDef,
    AuditCorrelation,
    Harness,
    HarnessToolCall,
    RunBudget,
    ToolCallBudget,
    ToolError,
    ToolOutcome,
    classify_error,
    load_agent_role,
    load_prompt,
)
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
from .review import ReviewSignals, derive_review_flags
from .types import AgentResult


def _model_facing_error(outcome: ToolOutcome) -> dict:
    """The error shape the *model* sees. Auth failures are redacted to 'not permitted' - the
    model gets no detail about why, while the audit trail keeps the real message (notes
    section 12)."""
    error = outcome.error
    assert error is not None
    message = "not permitted" if error.type == "auth" else error.message
    payload: dict = {"type": error.type, "message": message, "retryable": error.retryable}
    if error.code:
        payload["code"] = error.code
    return {"status": outcome.status, "error": payload}


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
    # Shared across the whole run (lead + every subagent). When exhausted, the agent stops
    # before its next model call.
    run_budget: RunBudget | None = None


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
    # Errors returned to the model but not subsequently recovered from feed the deterministic
    # needs_review derivation (notes section 16a). Tracked here, evaluated at return.
    unrecovered_errors: list[ToolError] = []

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

    def finish(status: str, text: str, last_stop_reason: str | None = None) -> AgentResult:
        """Builds the AgentResult and attaches the deterministically-derived review flags."""
        flags = derive_review_flags(
            ReviewSignals(
                status=status,  # type: ignore[arg-type]
                unrecovered_errors=unrecovered_errors,
                final_text=text,
                last_stop_reason=last_stop_reason,  # type: ignore[arg-type]
            )
        )
        return AgentResult(
            task_id=params.task_id,
            role=role.role,
            text=text,
            artifact_refs=artifact_refs,
            status=status,  # type: ignore[arg-type]
            needs_review=len(flags) > 0,
            review_flags=flags,
        )

    for turn in range(max_turns):
        # Session-level cost ceiling, checked before spend. Distinct from the per-agent
        # tool-call cap and delegation-depth cap - this bounds total tokens across the swarm.
        if params.run_budget is not None and params.run_budget.is_exhausted():
            params.tracer.end_span(agent_span, "partial", attributes={"stoppedReason": "run_budget_exhausted"})
            return finish("partial", "(stopped: run token budget exhausted)")

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
        if params.run_budget is not None:
            params.run_budget.record(result.usage)
        cost = compute_cost_usd(params.model.provider, params.model.model, result.usage)
        params.tracer.end_span(
            model_span,
            "ok",
            token_usage={"inputTokens": result.usage.input_tokens, "outputTokens": result.usage.output_tokens},
            cost_usd=cost,
        )
        messages.append(result.message)

        if result.stop_reason != "tool_use":
            params.tracer.end_span(agent_span, "ok")
            return finish("ok", text_of(result.message), result.stop_reason)

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

            # Exhausting the per-agent tool-call budget is a harness guarantee, not a tool
            # failure: the harness forces a terminal `rejected` outcome regardless of the model.
            try:
                budget.consume()
                outcome = await params.harness.execute(
                    role,
                    HarnessToolCall(
                        idempotency_key=call.id,
                        tool_name=call.name,
                        input=call.input,
                        delegation_depth=params.delegation_depth,
                        # trace_id / session_id share the tracer instance (one per run here);
                        # request_id is this agent invocation. Rotate the tracer per turn in a
                        # multi-turn conversation.
                        correlation=AuditCorrelation(
                            trace_id=params.tracer.trace_id,
                            session_id=params.tracer.trace_id,
                            request_id=params.task_id,
                        ),
                    ),
                    params.runtime,
                )
            except Exception as budget_error:  # noqa: BLE001 - converted to a rejected outcome
                outcome = ToolOutcome(status="rejected", error=classify_error(budget_error))

            if outcome.status == "ok":
                params.tracer.end_span(tool_span, "ok")
                if call.name == "write_artifact":
                    artifact_refs.append(outcome.output)
                tool_results.append(ToolResultBlock(tool_call_id=call.id, output=outcome.output))
            else:
                assert outcome.error is not None
                unrecovered_errors.append(outcome.error)
                params.tracer.end_span(
                    tool_span,
                    "error",
                    attributes={
                        "errorType": outcome.error.type,
                        "retryable": outcome.error.retryable,
                        "code": outcome.error.code,
                    },
                )
                tool_results.append(
                    ToolResultBlock(tool_call_id=call.id, output=_model_facing_error(outcome), is_error=True)
                )

        messages.append(ProviderMessage(role="tool", content=list(tool_results)))

    params.tracer.end_span(agent_span, "partial")
    return finish("partial", "(stopped: exceeded max turns before reaching a final answer)")
