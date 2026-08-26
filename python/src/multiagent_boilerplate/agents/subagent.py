from __future__ import annotations

from ..harness import Harness, RunBudget
from ..providers.types import ChatModel
from ..tools.types import ToolRuntime
from ..tracing.tracer import Tracer
from .run_agent import RunAgentParams, run_agent
from .types import AgentResult, AgentTask


async def run_subagent(
    task: AgentTask,
    model: ChatModel,
    harness: Harness,
    runtime: ToolRuntime,
    tracer: Tracer,
    delegation_depth: int,
    parent_span_id: str | None = None,
    run_budget: RunBudget | None = None,
) -> AgentResult:
    extra_system_context = "\n".join(
        [
            f"Objective: {task.objective}",
            f"Output format: {task.output_format}",
            f"Boundaries: {task.boundaries}",
        ]
    )

    return await run_agent(
        RunAgentParams(
            role_name="subagent",
            user_prompt=task.objective,
            model=model,
            harness=harness,
            runtime=runtime,
            tracer=tracer,
            task_id=task.task_id,
            delegation_depth=delegation_depth,
            parent_span_id=parent_span_id,
            extra_system_context=extra_system_context,
            max_turns=task.budget["maxToolCalls"] + 2,
            run_budget=run_budget,
        )
    )
