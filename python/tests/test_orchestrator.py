import tempfile
import uuid
from pathlib import Path

import pytest

from multiagent_boilerplate.agents.lead_agent import run_lead_agent
from multiagent_boilerplate.config import HarnessCaps
from multiagent_boilerplate.harness import Harness
from multiagent_boilerplate.orchestrator.orchestrator import Orchestrator, OrchestratorOptions
from multiagent_boilerplate.providers.mock import MockChatModel
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
            caps=HarnessCaps(max_subagents=8, max_delegation_depth=2, max_tool_calls_per_subagent=15),
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
            caps=HarnessCaps(max_subagents=1, max_delegation_depth=2, max_tool_calls_per_subagent=15),
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
