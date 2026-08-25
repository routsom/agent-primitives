#!/usr/bin/env python3
"""Stop hook: before ending the turn, run lint+test for whichever runtime(s) have uncommitted
changes. Skips a runtime entirely if it wasn't touched, so this stays fast on small edits.
Exits 2 (blocking, per Claude Code hook conventions) with failure details on stderr so the
agent fixes the issue before finishing rather than leaving a broken build behind.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def changed_paths() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line[3:].strip() for line in result.stdout.splitlines() if line.strip()]


def run(cmd: list[str], cwd: pathlib.Path) -> bool:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(f"$ {' '.join(cmd)} (in {cwd.relative_to(REPO_ROOT)})\n{result.stdout}{result.stderr}\n")
    return result.returncode == 0


def main() -> int:
    paths = changed_paths()
    ts_changed = any(p.startswith("typescript/") for p in paths)
    py_changed = any(p.startswith("python/") for p in paths)

    failures: list[str] = []

    if ts_changed:
        ts_dir = REPO_ROOT / "typescript"
        if not run(["npm", "run", "typecheck"], ts_dir):
            failures.append("typescript typecheck")
        if not run(["npm", "test"], ts_dir):
            failures.append("typescript tests")

    if py_changed:
        py_dir = REPO_ROOT / "python"
        if not run(["uv", "run", "ruff", "check", "."], py_dir):
            failures.append("python lint")
        if not run(["uv", "run", "pytest", "-q"], py_dir):
            failures.append("python tests")

    if failures:
        sys.stderr.write(f"\nStop hook checks failed: {', '.join(failures)}. Fix before finishing.\n")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
