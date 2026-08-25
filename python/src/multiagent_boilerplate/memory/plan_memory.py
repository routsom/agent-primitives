"""Persists the lead agent's plan before subagents are spawned, so a context truncation
mid-run doesn't lose the strategy (notes section 5). One plan file per run, keyed by run_id -
a durable job store in production would back this with a database instead of the filesystem,
but the interface (save/load by run_id) stays the same."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
