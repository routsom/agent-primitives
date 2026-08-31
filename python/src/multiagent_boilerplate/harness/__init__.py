"""Shared infrastructure every agent's tool call routes through - no agent-to-agent shortcut
around it (notes section 7). Validates scope, applies idempotency, executes, and returns a
typed ToolOutcome. Errors are classified here (transient/permanent/validation/auth) and
returned as data, never raised into the agent loop - so the orchestrator applies retry and
escalation policy from a structured field, not from parsing a message string."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..tools.types import Tool, ToolContext, ToolRuntime
from .approvals import ApprovalDecision, ApprovalProvider, ApprovalRequest, AutoApprove, ToolApprovalGate
from .audit import (
    AuditCorrelation,
    AuditEntry,
    AuditSink,
    ConsoleAuditSink,
    JsonlAuditSink,
    NoopAuditSink,
    now_iso,
    redact,
)
from .budget import (
    DelegationDepthExceededError,
    RunBudget,
    RunBudgetExceededError,
    SubagentCountExceededError,
    ToolCallBudget,
    ToolCallBudgetExceededError,
    assert_depth_within_cap,
    assert_subagent_count_within_cap,
)
from .circuit_breaker import CircuitBreakerOptions, ToolCircuitBreaker
from .errors import (
    AuthFailure,
    ClassifiedError,
    ToolError,
    ToolErrorType,
    ToolOutcome,
    ValidationFailure,
    classify_error,
)
from .idempotency import IdempotencyCache
from .rate_limit import SlidingWindowRateLimiter
from .schemas import load_agent_role, load_prompt, load_schema
from .scope import AgentRoleDef, HarnessScopeError, assert_can_spawn, assert_tool_allowed
from .validate import validate_agent_task, validate_artifact_ref, validate_trace_span

__all__ = [
    "Harness",
    "HarnessToolCall",
    "AgentRoleDef",
    "HarnessScopeError",
    "assert_tool_allowed",
    "assert_can_spawn",
    "DelegationDepthExceededError",
    "SubagentCountExceededError",
    "ToolCallBudget",
    "ToolCallBudgetExceededError",
    "RunBudget",
    "RunBudgetExceededError",
    "assert_depth_within_cap",
    "assert_subagent_count_within_cap",
    "IdempotencyCache",
    "SlidingWindowRateLimiter",
    "AuditCorrelation",
    "AuditEntry",
    "AuditSink",
    "ConsoleAuditSink",
    "JsonlAuditSink",
    "NoopAuditSink",
    "redact",
    "now_iso",
    "CircuitBreakerOptions",
    "ToolCircuitBreaker",
    "ApprovalDecision",
    "ApprovalProvider",
    "ApprovalRequest",
    "AutoApprove",
    "ToolApprovalGate",
    "Sanitizer",
    "HarnessOptions",
    "AuthFailure",
    "ClassifiedError",
    "ValidationFailure",
    "ToolError",
    "ToolErrorType",
    "ToolOutcome",
    "classify_error",
    "load_agent_role",
    "load_prompt",
    "load_schema",
    "validate_agent_task",
    "validate_artifact_ref",
    "validate_trace_span",
]


# Boundary guardrail seam (notes section 8, 19: "treat tool outputs as untrusted... sanitize
# at every boundary"). A deterministic, non-LLM hook applied to content crossing a trust
# boundary before it reaches the model. Default is identity - this ships the *seam* where
# app-specific rules go, not the rules themselves. See docs/extending.md.
Sanitizer = Callable[[str, Any], Any]


def _identity_sanitizer(_boundary: str, content: Any) -> Any:
    return content


@dataclass
class HarnessOptions:
    audit_sink: AuditSink | None = None
    circuit_breaker: CircuitBreakerOptions | None = None
    # Applied to every tool's output before it returns to the model. Default: identity.
    sanitize: Sanitizer | None = None
    # Human-in-the-loop gate for consequential tools. Default: AutoApprove (gates nothing).
    approvals: ApprovalProvider | None = None


@dataclass
class HarnessToolCall:
    idempotency_key: str
    tool_name: str
    input: dict[str, Any]
    delegation_depth: int
    # Correlation IDs for the audit log. When None, the audit entry uses empty ids.
    correlation: AuditCorrelation | None = None


class Harness:
    def __init__(self, tools: list[Tool], options: HarnessOptions | None = None) -> None:
        options = options or HarnessOptions()
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}
        self._idempotency = IdempotencyCache()
        self._audit_sink: AuditSink = options.audit_sink or NoopAuditSink()
        self._breaker = ToolCircuitBreaker(options.circuit_breaker)
        self._sanitize: Sanitizer = options.sanitize or _identity_sanitizer
        self._approvals: ApprovalProvider = options.approvals or AutoApprove()

    async def execute(self, role: AgentRoleDef, call: HarnessToolCall, runtime: ToolRuntime) -> ToolOutcome:
        outcome = await self._run(role, call, runtime)
        # 100%-coverage audit record, emitted for EVERY tool call regardless of outcome. Params
        # are redacted at this point of logging, never stored raw (notes section 22).
        self._audit_sink.record(
            AuditEntry(
                timestamp=now_iso(),
                trace_id=call.correlation.trace_id if call.correlation else "",
                session_id=call.correlation.session_id if call.correlation else "",
                request_id=call.correlation.request_id if call.correlation else "",
                agent_role=role.role,
                tool_name=call.tool_name,
                idempotency_key=call.idempotency_key,
                delegation_depth=call.delegation_depth,
                params_redacted=redact(call.input),  # type: ignore[arg-type]
                result_status=outcome.status,
                error_type=outcome.error.type if outcome.error else None,
            )
        )
        return outcome

    async def _run(self, role: AgentRoleDef, call: HarnessToolCall, runtime: ToolRuntime) -> ToolOutcome:
        # Pre-execution refusals classify as `rejected` (the harness said no, the tool never ran).
        try:
            assert_tool_allowed(role, call.tool_name)
        except Exception as error:  # noqa: BLE001 - returned as data, not propagated
            return ToolOutcome(status="rejected", error=classify_error(error))

        tool = self._tools.get(call.tool_name)
        if tool is None:
            unknown = ValidationFailure(f'harness: unknown tool "{call.tool_name}"')
            return ToolOutcome(status="rejected", error=classify_error(unknown))

        # Circuit breaker: if this tool's backend is failing system-wide, short-circuit
        # immediately as a transient error rather than piling on another timeout.
        if self._breaker.is_open(call.tool_name):
            transient = ClassifiedError("transient", f'tool "{call.tool_name}" circuit is open')
            return ToolOutcome(status="rejected", error=classify_error(transient))

        # Human-in-the-loop gate: a consequential tool cannot run without an explicit approval. A
        # denial is an authorization decision (classifies as `auth`: no retry, security-logged), so
        # the tool never executes. Pre-execution, so it counts as `rejected`, not `error`.
        if self._approvals.requires_approval(role.role, call.tool_name):
            decision = await self._approvals.decide(
                ApprovalRequest(
                    role=role.role,
                    tool_name=call.tool_name,
                    input=call.input,
                    idempotency_key=call.idempotency_key,
                    delegation_depth=call.delegation_depth,
                )
            )
            if decision != "approved":
                denied = AuthFailure(f'tool "{call.tool_name}" denied by approval gate')
                return ToolOutcome(status="rejected", error=classify_error(denied))

        async def run() -> Any:
            ctx = ToolContext(agent_role=role.role, delegation_depth=call.delegation_depth, runtime=runtime)
            return await tool.execute(call.input, ctx)

        # Post-execution failures classify as `error` (the tool ran and raised).
        try:
            output = await self._idempotency.run(call.idempotency_key, run)
            self._breaker.record_success(call.tool_name)
            return ToolOutcome(status="ok", output=self._sanitize("tool_output", output))
        except Exception as error:  # noqa: BLE001 - classified and returned as data
            self._breaker.record_failure(call.tool_name)
            return ToolOutcome(status="error", error=classify_error(error))

    def tool_definitions(self, role: AgentRoleDef) -> list[dict]:
        defs = []
        for name in role.allowed_tools:
            tool = self._tools.get(name)
            if tool is not None:
                defs.append({"name": tool.name, "description": tool.description, "input_schema": tool.input_schema})
        return defs
