"""Framework interop: you own the loop; a framework agent plugs in *underneath* it.

This boilerplate takes no position that frameworks are bad - they solve real problems. The
position is narrower: your orchestration, budgets, error policy, and audit trail should be yours,
and a framework agent should sit *below* that line as one governed unit of work, not above it
running your control loop. This example proves the line holds by pushing the same foreign agent
through the harness three ways and watching the harness - not the framework - decide what happens.

Runs offline; no framework dependency. In a real project the body of `_invoke_external_agent`
would be a LangGraph `graph.invoke(...)` or a CrewAI `crew.kickoff(...)`, and the adapter around
it would be unchanged - the framework owns its internal loop, we treat it as one opaque call.

    uv run python -m examples.framework_interop
"""

from __future__ import annotations

import asyncio
from typing import Any

from multiagent_boilerplate.harness import AgentRoleDef, Harness, HarnessToolCall
from multiagent_boilerplate.tools.types import ToolContext, ToolRuntime

TASK = "Compare orchestrator-worker and sequential-pipeline multi-agent topologies."


def _call(key: str) -> HarnessToolCall:
    return HarnessToolCall(idempotency_key=key, tool_name="framework_agent", input={"task": TASK}, delegation_depth=0)


async def _invoke_external_agent(task: str, fail_mode: str | None = None) -> dict[str, Any]:
    """Stand-in for an agent you already built in another framework (a LangGraph graph, a CrewAI
    crew). `fail_mode` simulates the two failure shapes such an agent typically throws, so the
    example can show the harness classifying them deterministically."""
    if fail_mode == "transient":
        raise RuntimeError("503 upstream model temporarily unavailable, please try again")
    if fail_mode == "permanent":
        raise RuntimeError("graph node 'retrieve' does not exist in the compiled workflow")
    return {
        "transcript": [
            f"[langgraph] node 'plan' -> decomposed task: {task}",
            "[langgraph] node 'retrieve' -> pulled 7 candidate passages",
            "[langgraph] node 'rank' -> kept top 3 by relevance",
            "[langgraph] node 'write' -> drafted answer, 2 revision loops",
        ],
        "answer": (
            "Orchestrator-worker parallelizes independent subtasks and isolates their contexts, "
            "at the cost of a fan-in/synthesis step; sequential-pipeline is simpler and cheaper "
            f"but serializes latency and lets errors compound stage to stage. (for: {task})"
        ),
    }


class FrameworkAgentTool:
    """The whole interop story in one adapter: a foreign framework agent, exposed to *our* lead
    agent as a single tool. Because it is an ordinary Tool, every call routes through the harness
    like any other - inheriting tool scoping, the tool-call budget, idempotency, the circuit
    breaker, deterministic error classification, and a trace span. The framework runs its own
    control loop *inside* `execute`; it never gets to run *ours*. We distill its verbose transcript
    to a one-line provenance summary rather than dumping it upward (see CLAUDE.md)."""

    name = "framework_agent"
    description = (
        "Delegate a research task to an external framework-based agent (e.g. a LangGraph graph or "
        "CrewAI crew). Returns a distilled summary and final answer."
    )
    input_schema = {"type": "object", "required": ["task"], "properties": {"task": {"type": "string"}}}
    exposable = True

    def __init__(self, fail_mode: str | None = None) -> None:
        self._fail_mode = fail_mode

    async def execute(self, input_: dict, ctx: ToolContext) -> dict:
        out = await _invoke_external_agent(input_["task"], self._fail_mode)
        steps = len(out["transcript"])
        return {"summary": f"external framework agent ran {steps} internal steps", "answer": out["answer"]}


class _NoRuntime:
    """A tool call never touches the runtime here, so a minimal no-op runtime is all the harness needs."""

    async def spawn_subagents(self, tasks: list[dict], depth: int) -> Any:
        raise RuntimeError("not used in this example")

    async def write_artifact(self, kind: str, summary: str, content: Any, created_by: str) -> Any:
        return {}

    async def read_artifact(self, artifact_id: str) -> Any:
        return {}

    async def save_plan(self, plan: Any) -> None:
        return None


# The lead's least-privilege scope: it may call the framework agent, listed like any native tool -
# the harness sees no difference between it and search_web.
_LEAD_ROLE = AgentRoleDef(
    role="lead",
    allowed_tools=["framework_agent"],
    can_spawn=["subagent"],
    max_delegation_depth=1,
    budget={"maxToolCalls": 10},
)


async def main() -> None:
    runtime: ToolRuntime = _NoRuntime()  # type: ignore[assignment]
    print("[framework-interop] a LangGraph/CrewAI-style agent, governed by our harness\n")

    # 1. Happy path: the harness runs the foreign agent and returns a distilled, typed result.
    harness = Harness([FrameworkAgentTool()])
    ok = await harness.execute(_LEAD_ROLE, _call("call-1"), runtime)
    print("1) governed call ->", ok.status, "\n   ", ok.output)

    # 2. Least-privilege scope: a role without framework_agent in allowed_tools is refused BEFORE
    #    the framework ever runs. The framework can't opt itself back in - our harness decides.
    unscoped = AgentRoleDef(
        role="lead", allowed_tools=["search_web"], can_spawn=[], max_delegation_depth=1, budget={"maxToolCalls": 10}
    )
    rejected = await harness.execute(unscoped, _call("call-2"), runtime)
    detail = f"({rejected.error.type}: {rejected.error.message})" if rejected.error else ""
    print("\n2) scope check ->", rejected.status, detail)

    # 3. Deterministic error classification: whatever the framework throws, the HARNESS decides the
    #    type and whether it is retryable - the model is never asked "should I retry?".
    for fail_mode in ("transient", "permanent"):
        flaky = Harness([FrameworkAgentTool(fail_mode)])
        outcome = await flaky.execute(_LEAD_ROLE, _call(f"call-{fail_mode}"), runtime)
        if outcome.error:
            err = outcome.error
            print(f"\n3) framework threw a {fail_mode} error")
            print(f'   -> harness classified it "{err.type}", retryable={err.retryable}')

    print(
        "\n[framework-interop] The framework ran its own loop inside one tool call. Ours stayed in "
        "charge of scope, error policy, and (in a full run) budget, tracing, and audit."
    )


if __name__ == "__main__":
    asyncio.run(main())
