"""Full orchestrator-worker flow end to end: a lead agent decomposes the query, spawns
parallel subagents (each with an isolated context), and a citation agent synthesizes their
distilled findings. Runs on the mock provider with zero API keys; set ANTHROPIC_API_KEY
(or OPENAI_API_KEY / GOOGLE_API_KEY with DEFAULT_PROVIDER set accordingly) to use a real
model instead.

Run with: uv run python -m examples.research_task
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from multiagent_boilerplate.agents.citation_agent import run_citation_agent
from multiagent_boilerplate.agents.lead_agent import run_lead_agent
from multiagent_boilerplate.config import load_config
from multiagent_boilerplate.harness import Harness, RunBudget
from multiagent_boilerplate.orchestrator.orchestrator import Orchestrator, OrchestratorOptions
from multiagent_boilerplate.providers import ResilienceOptions, resolve_resilient_model
from multiagent_boilerplate.tools.registry import build_tool_registry
from multiagent_boilerplate.tracing.tracer import Tracer


async def main() -> None:
    config = load_config()
    run_id = str(uuid.uuid4())
    model = resolve_resilient_model(
        config.default_provider,
        ResilienceOptions(
            timeout_ms=config.resilience.timeout_ms,
            max_retries=config.resilience.max_retries,
            base_delay_ms=config.resilience.base_delay_ms,
        ),
    )
    tracer = Tracer()
    harness = Harness(build_tool_registry())

    print(f'[research-task] run {run_id} using provider "{model.provider}" ({model.model})')

    turn_span = tracer.start_span("turn", "research-task")
    # One shared token ceiling for the whole run - lead + every subagent + citation count against it.
    run_budget = RunBudget(config.caps.max_run_tokens)

    orchestrator = Orchestrator(
        OrchestratorOptions(
            model=model,
            harness=harness,
            tracer=tracer,
            caps=config.caps,
            artifact_store_dir=str(Path(config.artifact_store_dir).resolve()),
            plan_memory_dir=str(Path(config.artifact_store_dir).resolve() / "plans"),
            run_id=run_id,
            parent_span_id=turn_span.span_id,
            run_budget=run_budget,
        )
    )

    query = "What are the main tradeoffs between orchestrator-worker and sequential-pipeline multi-agent topologies?"

    lead_result = await run_lead_agent(
        query=query,
        model=model,
        harness=harness,
        runtime=orchestrator,
        tracer=tracer,
        run_id=run_id,
        parent_span_id=turn_span.span_id,
        run_budget=run_budget,
    )

    print("\n[lead agent result]")
    print(lead_result.text)

    citation_result = await run_citation_agent(
        findings=[lead_result],
        model=model,
        harness=harness,
        runtime=orchestrator,
        tracer=tracer,
        run_id=run_id,
        run_budget=run_budget,
        parent_span_id=turn_span.span_id,
    )

    tracer.end_span(turn_span, "ok")

    print("\n[citation agent result]")
    print(citation_result.text)
    ceiling = config.caps.max_run_tokens or "unlimited"
    print(
        f"\n[research-task] done. {len(tracer.all_spans())} spans recorded, "
        f"{run_budget.consumed} tokens spent (ceiling {ceiling})."
    )


if __name__ == "__main__":
    asyncio.run(main())
