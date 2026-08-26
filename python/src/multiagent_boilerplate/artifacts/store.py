"""The seam for artifact persistence. LocalArtifactStore is the shipped default; implement the
same two-method ArtifactStore protocol against S3/GCS/a database and pass it to the orchestrator
to swap backends (see docs/extending.md). Callers only ever see an artifact reference dict,
never a storage-specific type (notes section 4-5)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..harness.validate import validate_artifact_ref


@runtime_checkable
class ArtifactStore(Protocol):
    async def write(self, kind: str, summary: str, content: Any, created_by: str) -> dict: ...
    async def read(self, artifact_id: str) -> Any: ...


class LocalArtifactStore:
    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)

    async def write(self, kind: str, summary: str, content: Any, created_by: str) -> dict:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        artifact_id = str(uuid.uuid4())
        path = self._root_dir / f"{artifact_id}.json"
        serialized = json.dumps(content, indent=2)
        path.write_text(serialized, encoding="utf-8")

        ref = {
            "artifactId": artifact_id,
            "kind": kind,
            "sizeBytes": len(serialized.encode("utf-8")),
            "createdBy": created_by,
            "createdAt": datetime.now(UTC).isoformat(),
            "summary": summary,
            "uri": f"file://{path}",
        }
        validate_artifact_ref(ref)
        return ref

    async def read(self, artifact_id: str) -> Any:
        path = self._root_dir / f"{artifact_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))
