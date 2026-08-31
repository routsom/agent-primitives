"""Human-in-the-loop approval gate: a gated tool cannot run without an explicit approval."""

from __future__ import annotations

from multiagent_boilerplate.harness import (
    AgentRoleDef,
    ApprovalRequest,
    Harness,
    HarnessOptions,
    HarnessToolCall,
    ToolApprovalGate,
)
from multiagent_boilerplate.tools.types import ToolContext


class _NoRuntime:
    async def spawn_subagents(self, tasks, depth):  # noqa: ANN001, ANN201
        raise RuntimeError("n/a")

    async def write_artifact(self, kind, summary, content, created_by):  # noqa: ANN001, ANN201
        return {}

    async def read_artifact(self, artifact_id):  # noqa: ANN001, ANN201
        return {}

    async def save_plan(self, plan):  # noqa: ANN001, ANN201
        return None


class SendEmailTool:
    name = "send_email"
    description = "sends an email (consequential)"
    input_schema = {"type": "object"}
    exposable = True

    def __init__(self) -> None:
        self.sent = 0

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        self.sent += 1
        return {"sent": True}


_ROLE = AgentRoleDef(
    role="subagent", allowed_tools=["send_email"], can_spawn=[], max_delegation_depth=0, budget={"maxToolCalls": 100}
)


def _call(key: str) -> HarnessToolCall:
    return HarnessToolCall(idempotency_key=key, tool_name="send_email", input={"to": "x@y.z"}, delegation_depth=0)


async def test_denied_gate_blocks_tool() -> None:
    tool = SendEmailTool()

    async def deny(_req: ApprovalRequest) -> str:
        return "denied"

    harness = Harness([tool], HarnessOptions(approvals=ToolApprovalGate(["send_email"], deny)))
    outcome = await harness.execute(_ROLE, _call("a"), _NoRuntime())
    assert outcome.status == "rejected"
    assert outcome.error is not None and outcome.error.type == "auth"
    assert tool.sent == 0


async def test_approved_gate_runs_tool_and_passes_request() -> None:
    tool = SendEmailTool()
    seen: list[ApprovalRequest] = []

    async def approve(req: ApprovalRequest) -> str:
        seen.append(req)
        return "approved"

    harness = Harness([tool], HarnessOptions(approvals=ToolApprovalGate(["send_email"], approve)))
    outcome = await harness.execute(_ROLE, _call("b"), _NoRuntime())
    assert outcome.status == "ok"
    assert tool.sent == 1
    assert seen[0].tool_name == "send_email"
    assert seen[0].input == {"to": "x@y.z"}


async def test_ungated_tool_is_not_blocked() -> None:
    tool = SendEmailTool()

    async def deny(_req: ApprovalRequest) -> str:
        return "denied"

    harness = Harness([tool], HarnessOptions(approvals=ToolApprovalGate(["some_other_tool"], deny)))
    outcome = await harness.execute(_ROLE, _call("c"), _NoRuntime())
    assert outcome.status == "ok"
    assert tool.sent == 1
