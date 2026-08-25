"""LLM-as-judge, single call, multi-criteria rubric (notes section 10; specs/prompts/judge.md)."""

from __future__ import annotations

import json

from ..agents.run_agent import RunAgentParams, run_agent
from ..harness import Harness
from ..providers.types import ChatModel
from ..tools.types import ToolRuntime
from ..tracing.tracer import Tracer


async def run_judge(
    task: str,
    response: str,
    trace_summary: str,
    model: ChatModel,
    harness: Harness,
    runtime: ToolRuntime,
    tracer: Tracer,
    eval_id: str,
) -> dict:
    user_prompt = "\n\n".join(
        [f"Original task: {task}", f"Final response: {response}", f"Trace summary: {trace_summary}"]
    )

    result = await run_agent(
        RunAgentParams(
            role_name="judge",
            user_prompt=user_prompt,
            model=model,
            harness=harness,
            runtime=runtime,
            tracer=tracer,
            task_id=eval_id,
            delegation_depth=0,
        )
    )

    try:
        return json.loads(result.text)
    except json.JSONDecodeError as error:
        raise ValueError(f"judge did not return valid JSON: {result.text}") from error
