#!/usr/bin/env python3
"""PostToolUse hook: lint the single file just edited, per-language, and give fast feedback.

Reads the tool call payload Claude Code sends on stdin, figures out which runtime the edited
file belongs to, and runs that runtime's linter scoped to just that file. Exits non-zero (and
prints to stderr) on lint failure so Claude Code surfaces it and can self-correct immediately,
rather than the mistake surviving until CI.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0

    path = pathlib.Path(file_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return 0
    path = path.resolve()

    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return 0

    parts = rel.parts
    if not parts:
        return 0

    if parts[0] == "typescript" and path.suffix in (".ts", ".tsx"):
        result = subprocess.run(
            ["npx", "eslint", "--no-warn-ignored", str(path)],
            cwd=REPO_ROOT / "typescript",
            capture_output=True,
            text=True,
        )
    elif parts[0] == "python" and path.suffix == ".py":
        result = subprocess.run(
            ["uv", "run", "ruff", "check", str(path)],
            cwd=REPO_ROOT / "python",
            capture_output=True,
            text=True,
        )
    else:
        return 0

    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
