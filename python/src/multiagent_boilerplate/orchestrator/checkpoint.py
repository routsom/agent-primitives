"""The seam for durable, resumable execution (notes section 12). The expensive unit of work in
an orchestrator-worker run is a subagent; when a swarm dies partway through fan-out, resuming
should skip the subagents that already finished and re-run only the missing ones. A checkpoint is
one such completed unit, keyed by (run_id, task_id).

CheckpointMemory (local filesystem) is the shipped default; a production durable-job store (a
database, a workflow engine like Temporal) implements this same save/load-by-key contract.
Mirrors specs/schemas/run-checkpoint.schema.json. See docs/extending.md."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import quote

from ..agents.types import AgentResult


@runtime_checkable
class CheckpointStore(Protocol):
    """Persist and restore completed subagent results by (run_id, task_id)."""

    async def save(self, run_id: str, task_id: str, result: AgentResult) -> None: ...
    async def load(self, run_id: str, task_id: str) -> AgentResult | None: ...


class CheckpointMemory:
    """Local filesystem checkpoint store (default). One file per (run_id, task_id)."""

    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)

    def _path(self, run_id: str, task_id: str) -> Path:
        # task_id is validated against the agent-task schema before it reaches here; encode anyway
        # so an unusual id can never escape the checkpoint directory.
        return self._root_dir / f"{run_id}.{quote(task_id, safe='')}.checkpoint.json"

    async def save(self, run_id: str, task_id: str, result: AgentResult) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "runId": run_id,
            "taskId": task_id,
            "savedAt": datetime.now(UTC).isoformat(),
            "result": asdict(result),
        }
        self._path(run_id, task_id).write_text(json.dumps(record, indent=2), encoding="utf-8")

    async def load(self, run_id: str, task_id: str) -> AgentResult | None:
        path = self._path(run_id, task_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))["result"]
        return AgentResult(**data)
