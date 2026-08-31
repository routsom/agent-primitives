"""Implements ToolRuntime.spawn_subagents: parallel fan-out/fan-in with the two circuit
breakers from the notes (delegation-depth cap, per-subagent retry cap) and an explicit
partial-completion policy - proceed with what succeeded, flag the gap, never silently present
partial results as complete (notes section 9, diagrams section 3)."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..agents.subagent import run_subagent
from ..agents.types import AgentResult, AgentTask
from ..artifacts.store import ArtifactStore, LocalArtifactStore
from ..config import HarnessCaps
from ..harness import (
    Harness,
    RunBudget,
    assert_depth_within_cap,
    assert_subagent_count_within_cap,
    validate_agent_task,
)
from ..memory.plan_memory import PlanMemory, PlanStore
from ..providers.types import ChatModel
from ..tracing.tracer import Tracer
from .checkpoint import CheckpointMemory, CheckpointStore


@dataclass
class OrchestratorOptions:
    model: ChatModel
    harness: Harness
    tracer: Tracer
    caps: HarnessCaps
    artifact_store_dir: str
    plan_memory_dir: str
    run_id: str
    parent_span_id: str | None = None
    subagent_retries: int = 2
    # Shared session token ceiling; the same instance is passed to the lead and citation agents.
    run_budget: RunBudget | None = None
    # Override the default local-filesystem stores with your own backend (S3, a database, etc.).
    artifact_store: ArtifactStore | None = None
    plan_store: PlanStore | None = None
    checkpoint_store: CheckpointStore | None = None
    # Where the default local checkpoint store writes. Defaults to `<artifact_store_dir>/checkpoints`.
    checkpoint_dir: str | None = None


class Orchestrator:
    def __init__(self, opts: OrchestratorOptions) -> None:
        self._opts = opts
        self._artifact_store: ArtifactStore = opts.artifact_store or LocalArtifactStore(opts.artifact_store_dir)
        self._plan_memory: PlanStore = opts.plan_store or PlanMemory(opts.plan_memory_dir)
        self._checkpoint_store: CheckpointStore = opts.checkpoint_store or CheckpointMemory(
            opts.checkpoint_dir or str(Path(opts.artifact_store_dir) / "checkpoints")
        )

    async def spawn_subagents(self, raw_tasks: list[dict], depth: int) -> dict[str, Any]:
        assert_subagent_count_within_cap(len(raw_tasks), self._opts.caps.max_subagents)
        assert_depth_within_cap(depth, self._opts.caps.max_delegation_depth)

        tasks: list[AgentTask] = []
        for raw in raw_tasks:
            validate_agent_task(raw)
            tasks.append(AgentTask.from_schema_dict(raw))

        results = await asyncio.gather(*(self._run_or_restore(task, depth) for task in tasks))
        partial = any(r.status != "ok" for r in results)
        # Cross the tool-result boundary as plain dicts, not dataclass instances - provider
        # adapters serialize tool output to JSON/text, mirroring the TS runtime where
        # AgentResult is a plain object rather than a class instance.
        return {"results": [asdict(r) for r in results], "partial": partial}

    async def write_artifact(self, kind: str, summary: str, content: Any, created_by: str) -> dict:
        return await self._artifact_store.write(kind=kind, summary=summary, content=content, created_by=created_by)

    async def read_artifact(self, artifact_id: str) -> Any:
        return await self._artifact_store.read(artifact_id)

    async def save_plan(self, plan: Any) -> None:
        await self._plan_memory.save(self._opts.run_id, plan)

    async def load_plan(self) -> Any | None:
        return await self._plan_memory.load(self._opts.run_id)

    async def _run_or_restore(self, task: AgentTask, depth: int) -> AgentResult:
        """Durable, resumable execution (notes section 12). Before running a subagent, look for a
        checkpoint from an earlier attempt at this same run_id; if one exists the work is restored
        instead of recomputed - a resumed swarm re-runs only the tasks that never finished. A
        successful result is checkpointed so the next resume skips it. Only 'ok' results are
        checkpointed: a partial or errored result is deliberately left uncheckpointed so it re-runs."""
        restored = await self._checkpoint_store.load(self._opts.run_id, task.task_id)
        if restored is not None:
            # Emit a subagent-level span so a resumed run's trace still shows this unit of work,
            # flagged as restored rather than executed. Fresh runs never hit this path.
            span = self._opts.tracer.start_span(
                "agent",
                f"{task.role}:{task.task_id}",
                parent_span_id=self._opts.parent_span_id,
                agent_role=task.role,
                delegation_depth=depth,
            )
            self._opts.tracer.end_span(span, "ok", attributes={"restoredFromCheckpoint": True})
            return restored

        result = await self._run_with_retry(task, depth)
        if result.status == "ok":
            await self._checkpoint_store.save(self._opts.run_id, task.task_id, result)
        return result

    async def _run_with_retry(self, task: AgentTask, depth: int, attempts_left: int | None = None) -> AgentResult:
        attempts_left = self._opts.subagent_retries if attempts_left is None else attempts_left
        try:
            return await run_subagent(
                task=task,
                model=self._opts.model,
                harness=self._opts.harness,
                runtime=self,
                tracer=self._opts.tracer,
                delegation_depth=depth,
                parent_span_id=self._opts.parent_span_id,
                run_budget=self._opts.run_budget,
            )
        except Exception as error:  # noqa: BLE001 - retried deterministically, then reported as partial
            if attempts_left > 1:
                return await self._run_with_retry(task, depth, attempts_left - 1)
            return AgentResult(
                task_id=task.task_id,
                role=task.role,
                text=f"subagent failed after retries: {error}",
                artifact_refs=[],
                status="error",
                needs_review=True,
                review_flags=["subagent_crashed"],
            )
