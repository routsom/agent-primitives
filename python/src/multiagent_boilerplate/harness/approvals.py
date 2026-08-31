"""Human-in-the-loop approval gate (notes section 6-7, 12). Some tool calls are too consequential
to let a model make unsupervised - a payment, a destructive write, an email to a customer. The
gate lives in the harness, alongside scope and budgets, for the same reason those do: it's a
guarantee no prompt can route around. A gated tool cannot execute without an explicit `approved`
decision, full stop.

The decision itself is a seam. `decide` may block awaiting a human (wire it to a queue + UI), or
read a decision recorded earlier - which is how this composes with durable execution: a resolver
that suspends the run, persists via the checkpoint store, and returns once a human answers. The
shipped default gates nothing, so existing runs are unchanged."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

ApprovalDecision = Literal["approved", "denied"]


@dataclass
class ApprovalRequest:
    role: str
    tool_name: str
    input: dict
    idempotency_key: str
    delegation_depth: int


@runtime_checkable
class ApprovalProvider(Protocol):
    """Does this (role, tool) require approval, and if so, what's the decision?"""

    def requires_approval(self, role: str, tool_name: str) -> bool: ...
    async def decide(self, request: ApprovalRequest) -> ApprovalDecision: ...


class AutoApprove:
    """Default: nothing needs approval - the harness behaves exactly as before."""

    def requires_approval(self, role: str, tool_name: str) -> bool:
        return False

    async def decide(self, request: ApprovalRequest) -> ApprovalDecision:
        return "approved"


class ToolApprovalGate:
    """Gate a fixed set of tool names; delegate the actual approve/deny to an injected resolver (a
    prompt, a web approval queue, a policy check). The resolver is where your product's HITL UX
    lives; the gate just guarantees it's consulted."""

    def __init__(
        self, gated_tools: list[str], resolver: Callable[[ApprovalRequest], Awaitable[ApprovalDecision]]
    ) -> None:
        self._gated_tools = gated_tools
        self._resolver = resolver

    def requires_approval(self, role: str, tool_name: str) -> bool:
        return tool_name in self._gated_tools

    async def decide(self, request: ApprovalRequest) -> ApprovalDecision:
        return await self._resolver(request)
