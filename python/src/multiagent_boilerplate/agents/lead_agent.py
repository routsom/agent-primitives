from __future__ import annotations

from ..harness import Harness
from ..providers.types import ChatModel
from ..tools.types import ToolRuntime
from ..tracing.tracer import Tracer
from .run_agent import RunAgentParams, run_agent
from .types import AgentResult


async def run_lead_agent(
    query: str,
    model: ChatModel,
    harness: Harness,
    runtime: ToolRuntime,
    tracer: Tracer,
    run_id: str,
    parent_span_id: str | None = None,
) -> AgentResult:
    return await run_agent(
        RunAgentParams(
            role_name="lead",
            user_prompt=query,
            model=model,
            harness=harness,
            runtime=runtime,
            tracer=tracer,
            task_id=run_id,
            delegation_depth=0,
            parent_span_id=parent_span_id,
        )
    )
