import tempfile
import uuid
from pathlib import Path

import pytest

from multiagent_boilerplate.agents.lead_agent import run_lead_agent
from multiagent_boilerplate.config import HarnessCaps
from multiagent_boilerplate.harness import Harness
from multiagent_boilerplate.orchestrator.checkpoint import CheckpointMemory
from multiagent_boilerplate.orchestrator.orchestrator import Orchestrator, OrchestratorOptions
from multiagent_boilerplate.providers.mock import MockChatModel
from multiagent_boilerplate.providers.types import ChatCompletionRequest, ChatCompletionResult
from multiagent_boilerplate.tools.registry import build_tool_registry
from multiagent_boilerplate.tracing.tracer import Tracer


@pytest.fixture
def work_dir():
    with tempfile.TemporaryDirectory(prefix="multiagent-boilerplate-test-") as d:
        yield Path(d)


async def test_spawns_subagents_writes_artifacts_and_synthesizes(work_dir: Path) -> None:
    model = MockChatModel()
    harness = Harness(build_tool_registry())
    tracer = Tracer(on_span_end=lambda _span: None)
    run_id = str(uuid.uuid4())
    turn_span = tracer.start_span("turn", "test-run")

    orchestrator = Orchestrator(
        OrchestratorOptions(
            model=model,
            harness=harness,
            tracer=tracer,
            caps=HarnessCaps(max_subagents=8, max_delegation_depth=2, max_tool_calls_per_subagent=15, max_run_tokens=0),
            artifact_store_dir=str(work_dir / "artifacts"),
            plan_memory_dir=str(work_dir / "plans"),
            run_id=run_id,
            parent_span_id=turn_span.span_id,
        )
    )

    result = await run_lead_agent(
        query="Compare orchestrator-worker and sequential-pipeline topologies.",
        model=model,
        harness=harness,
        runtime=orchestrator,
        tracer=tracer,
        run_id=run_id,
        parent_span_id=turn_span.span_id,
    )
    tracer.end_span(turn_span, "ok")

    assert result.status == "ok"
    assert len(result.text) > 0

    spans = tracer.all_spans()
    assert any(s.kind == "agent" and s.agent_role == "lead" for s in spans)
    assert any(s.kind == "agent" and s.agent_role == "subagent" for s in spans)
    assert any(s.kind == "tool_call" and s.name == "spawn_subagents" for s in spans)
    assert any(s.kind == "tool_call" and s.name == "write_artifact" for s in spans)


async def test_rejects_spawn_request_exceeding_subagent_cap(work_dir: Path) -> None:
    model = MockChatModel()
    harness = Harness(build_tool_registry())
    tracer = Tracer(on_span_end=lambda _span: None)

    orchestrator = Orchestrator(
        OrchestratorOptions(
            model=model,
            harness=harness,
            tracer=tracer,
            caps=HarnessCaps(max_subagents=1, max_delegation_depth=2, max_tool_calls_per_subagent=15, max_run_tokens=0),
            artifact_store_dir=str(work_dir / "artifacts"),
            plan_memory_dir=str(work_dir / "plans"),
            run_id=str(uuid.uuid4()),
        )
    )

    task = {
        "taskId": "a",
        "role": "subagent",
        "objective": "x",
        "outputFormat": "y",
        "allowedTools": ["search_web"],
        "boundaries": "z",
        "budget": {"maxToolCalls": 5},
    }

    with pytest.raises(Exception):  # noqa: B017 - asserting the harness cap rejects, not a specific class
        await orchestrator.spawn_subagents([task, task], 1)


_CAPS = HarnessCaps(max_subagents=8, max_delegation_depth=2, max_tool_calls_per_subagent=15, max_run_tokens=0)
_TASK = {
    "taskId": "sub-1",
    "role": "subagent",
    "objective": "Investigate angle A of the topic",
    "outputFormat": "bullet list",
    "allowedTools": ["search_web", "write_artifact"],
    "boundaries": "Angle A only.",
    "budget": {"maxToolCalls": 15, "maxDelegationDepth": 0},
}


class _ThrowingModel:
    """Fails on every call - stands in for 'the subagent would re-run and cost tokens'."""

    provider = "mock"
    model = "throws"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        raise RuntimeError("model must not be called when a checkpoint exists")


def _orchestrator_for(model: object, run_id: str, tracer: Tracer, work_dir: Path) -> Orchestrator:
    return Orchestrator(
        OrchestratorOptions(
            model=model,
            harness=Harness(build_tool_registry()),
            tracer=tracer,
            caps=_CAPS,
            artifact_store_dir=str(work_dir / "artifacts"),
            plan_memory_dir=str(work_dir / "plans"),
            checkpoint_dir=str(work_dir / "checkpoints"),
            run_id=run_id,
        )
    )


async def test_restores_completed_subagent_on_resume(work_dir: Path) -> None:
    run_id = str(uuid.uuid4())

    # First run: succeeds and writes a checkpoint.
    first_run = _orchestrator_for(MockChatModel(), run_id, Tracer(on_span_end=lambda _s: None), work_dir)
    first = await first_run.spawn_subagents([_TASK], 1)
    assert first["results"][0]["status"] == "ok"
    assert await CheckpointMemory(work_dir / "checkpoints").load(run_id, "sub-1") is not None

    # Resume with a model that throws: if the subagent re-ran, this would error. Restore avoids it.
    tracer = Tracer(on_span_end=lambda _s: None)
    second = await _orchestrator_for(_ThrowingModel(), run_id, tracer, work_dir).spawn_subagents([_TASK], 1)
    assert second["partial"] is False
    assert second["results"][0]["status"] == "ok"
    assert second["results"][0]["text"] == first["results"][0]["text"]
    assert any((s.attributes or {}).get("restoredFromCheckpoint") is True for s in tracer.all_spans())


async def test_does_not_checkpoint_failed_subagent(work_dir: Path) -> None:
    run_id = str(uuid.uuid4())

    # First run fails outright - nothing should be checkpointed.
    failed_run = _orchestrator_for(_ThrowingModel(), run_id, Tracer(on_span_end=lambda _s: None), work_dir)
    failed = await failed_run.spawn_subagents([_TASK], 1)
    assert failed["results"][0]["status"] == "error"
    assert await CheckpointMemory(work_dir / "checkpoints").load(run_id, "sub-1") is None

    # Resume with a working model: because nothing was checkpointed, it actually runs and succeeds.
    recovered_run = _orchestrator_for(MockChatModel(), run_id, Tracer(on_span_end=lambda _s: None), work_dir)
    recovered = await recovered_run.spawn_subagents([_TASK], 1)
    assert recovered["results"][0]["status"] == "ok"
