"""Loads specs/ files - the single source of truth shared with the TypeScript runtime."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path


def _find_repo_root(start_dir: Path) -> Path:
    """Walks up from this module's actual location until it finds `specs/schemas` -
    deliberately not a fixed parent-count, so this keeps working regardless of how deep this
    file sits relative to the repo root. A deployment must keep `specs/` as a sibling of
    `python/` on disk either way - see deploy/Dockerfile.python - this just stops assuming a
    specific directory depth to find it."""
    directory = start_dir
    while True:
        if (directory / "specs" / "schemas").is_dir():
            return directory
        if directory.parent == directory:
            raise RuntimeError(f"could not locate repo root (no ancestor of {start_dir} contains specs/schemas)")
        directory = directory.parent


REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)
SCHEMAS_DIR = REPO_ROOT / "specs" / "schemas"
AGENTS_DIR = REPO_ROOT / "specs" / "agents"


@cache
def load_schema(file_name: str) -> dict:
    return json.loads((SCHEMAS_DIR / file_name).read_text(encoding="utf-8"))


@cache
def load_agent_role(role_name: str) -> dict:
    return json.loads((AGENTS_DIR / f"{role_name}.json").read_text(encoding="utf-8"))


@cache
def load_prompt(prompt_relative_path: str) -> str:
    return (REPO_ROOT / prompt_relative_path).read_text(encoding="utf-8")
