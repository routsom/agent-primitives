from __future__ import annotations

from ..harness import Harness
from ..providers.types import ChatModel
from ..tools.types import ToolRuntime
from ..tracing.tracer import Tracer
from .run_agent import RunAgentParams, run_agent
from .types import AgentResult


async def run_citation_agent(
    findings: list[AgentResult],
    model: ChatModel,
    harness: Harness,
    runtime: ToolRuntime,
    tracer: Tracer,
    run_id: str,
    parent_span_id: str | None = None,
) -> AgentResult:
    findings_text = "\n\n".join(
        f"[{f.task_id}] ({f.status}) {f.text}"
        + (f" refs: {', '.join(r['artifactId'] for r in f.artifact_refs)}" if f.artifact_refs else "")
        for f in findings
    )

    return await run_agent(
        RunAgentParams(
            role_name="citation",
            user_prompt=findings_text,
            model=model,
            harness=harness,
            runtime=runtime,
            tracer=tracer,
            task_id=f"{run_id}-citation",
            delegation_depth=0,
            parent_span_id=parent_span_id,
        )
    )
