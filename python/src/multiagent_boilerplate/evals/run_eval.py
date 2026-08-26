"""Runs the seed task set end to end and scores each with the LLM judge. CI-runnable on the
mock provider; point DEFAULT_PROVIDER at a real model to eval actual behavior. Start small
and early per notes section 10 - this seed set is a starting point, not a finished suite."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from ..agents.lead_agent import run_lead_agent
from ..config import load_config
from ..harness import Harness, RunBudget
from ..orchestrator.orchestrator import Orchestrator, OrchestratorOptions
from ..providers import ResilienceOptions, resolve_resilient_model
from ..tools.registry import build_tool_registry
from ..tracing.tracer import Tracer
from .judge import run_judge

SEED_TASKS_PATH = Path(__file__).resolve().parent / "seed_tasks.json"


async def main() -> None:
    config = load_config()
    model = resolve_resilient_model(
        config.default_provider,
        ResilienceOptions(
            timeout_ms=config.resilience.timeout_ms,
            max_retries=config.resilience.max_retries,
            base_delay_ms=config.resilience.base_delay_ms,
        ),
    )
    harness = Harness(build_tool_registry())
    seed_tasks = json.loads(SEED_TASKS_PATH.read_text(encoding="utf-8"))

    flagged = 0

    for seed in seed_tasks:
        run_id = str(uuid.uuid4())
        tracer = Tracer(on_span_end=lambda _span: None)
        turn_span = tracer.start_span("turn", seed["id"])

        run_budget = RunBudget(config.caps.max_run_tokens)
        orchestrator = Orchestrator(
            OrchestratorOptions(
                model=model,
                harness=harness,
                tracer=tracer,
                caps=config.caps,
                artifact_store_dir=str(Path(config.artifact_store_dir) / "evals"),
                plan_memory_dir=str(Path(config.artifact_store_dir) / "evals" / "plans"),
                run_id=run_id,
                parent_span_id=turn_span.span_id,
                run_budget=run_budget,
            )
        )

        lead_result = await run_lead_agent(
            query=seed["query"],
            model=model,
            harness=harness,
            runtime=orchestrator,
            tracer=tracer,
            run_id=run_id,
            parent_span_id=turn_span.span_id,
            run_budget=run_budget,
        )
        tracer.end_span(turn_span, "ok")

        kinds = sorted({s.kind for s in tracer.all_spans()})
        trace_summary = f"{len(tracer.all_spans())} spans, kinds: {', '.join(kinds)}"

        verdict = await run_judge(
            task=seed["query"],
            response=lead_result.text,
            trace_summary=trace_summary,
            model=model,
            harness=harness,
            runtime=orchestrator,
            tracer=tracer,
            eval_id=f"{seed['id']}-judge",
        )

        # Triggered review (notes section 16a): the run's own deterministic review flags force
        # a human-review flag regardless of what the judge concluded - a structural signal is a
        # hard trigger, not a soft opinion.
        forced = lead_result.needs_review
        flag = verdict.get("flag_for_human_review") or forced
        if flag:
            flagged += 1
        if forced:
            flag_note = f" (FLAGGED - structural: {', '.join(lead_result.review_flags)})"
        elif verdict.get("flag_for_human_review"):
            flag_note = " (FLAGGED by judge)"
        else:
            flag_note = ""
        print(f"[eval] {seed['id']}: {json.dumps(verdict['scores'])}{flag_note}")

    print(f"\n[eval] {len(seed_tasks)} tasks run, {flagged} flagged for human review.")


if __name__ == "__main__":
    asyncio.run(main())
