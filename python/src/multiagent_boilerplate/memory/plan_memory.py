"""Persists the lead agent's plan before subagents are spawned, so a context truncation
mid-run doesn't lose the strategy (notes section 5). One plan file per run, keyed by run_id -
a durable job store in production would back this with a database instead of the filesystem,
but the interface (save/load by run_id) stays the same."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PlanStore(Protocol):
    """The seam for durable plan storage. PlanMemory (local filesystem) is the shipped default;
    a production durable-job store would implement this same interface against a database."""

    async def save(self, run_id: str, plan: Any) -> None: ...
    async def load(self, run_id: str) -> Any | None: ...


class PlanMemory:
    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)

    async def save(self, run_id: str, plan: Any) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        path = self._root_dir / f"{run_id}.plan.json"
        path.write_text(
            json.dumps({"savedAt": datetime.now(UTC).isoformat(), "plan": plan}, indent=2), encoding="utf-8"
        )

    async def load(self, run_id: str) -> Any | None:
        path = self._root_dir / f"{run_id}.plan.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8")).get("plan")
