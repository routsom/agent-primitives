#!/usr/bin/env python3
"""Cross-language parity check: runs the research-task example in both typescript/ and
python/ against the mock provider, and asserts they produce structurally equivalent trace
span trees - same span kinds, names (modulo run-specific ids), roles, delegation depths, and
statuses, correctly nested. This is what CLAUDE.md/CONTRIBUTING.md mean by "the parity test" -
it's what actually catches a specs/ behavior change applied to only one runtime.

Comparison is by tree shape, not by the flat order spans were logged in: parallel subagents
race independently in Node's event loop vs. Python's asyncio, so which one logs first isn't
meaningful and shouldn't fail the check - but which spans nest under which parent is.

Run from the repository root: python3 scripts/check_parity.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TRACE_PREFIX = "[trace] "


def run_ts(artifact_dir: Path) -> str:
    env = {**os.environ, "DEFAULT_PROVIDER": "mock", "ARTIFACT_STORE_DIR": str(artifact_dir)}
    result = subprocess.run(
        ["npm", "run", "--silent", "example:research"],
        cwd=REPO_ROOT / "typescript",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def run_py(artifact_dir: Path) -> str:
    env = {**os.environ, "DEFAULT_PROVIDER": "mock", "ARTIFACT_STORE_DIR": str(artifact_dir)}
    result = subprocess.run(
        ["uv", "run", "python", "-m", "examples.research_task"],
        cwd=REPO_ROOT / "python",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def parse_spans(stdout: str) -> list[dict]:
    spans = []
    for line in stdout.splitlines():
        if line.startswith(TRACE_PREFIX):
            spans.append(json.loads(line[len(TRACE_PREFIX) :]))
    return spans


def own_signature(span: dict) -> tuple:
    return (
        span["kind"],
        ID_PATTERN.sub("<id>", span["name"]),
        span.get("agentRole"),
        span["delegationDepth"],
        span["status"],
    )


def tree_signature(spans: list[dict]) -> Any:
    by_id = {s["spanId"]: s for s in spans}
    children: dict[str | None, list[str]] = {}
    for s in spans:
        children.setdefault(s.get("parentSpanId"), []).append(s["spanId"])

    roots = children.get(None, [])
    if len(roots) != 1:
        raise ValueError(f"expected exactly one root span (parentSpanId=None), found {len(roots)}")

    def build(span_id: str) -> tuple:
        span = by_id[span_id]
        child_sigs = sorted(build(child_id) for child_id in children.get(span_id, []))
        return (own_signature(span), tuple(child_sigs))

    return build(roots[0])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="parity-ts-") as ts_dir, tempfile.TemporaryDirectory(prefix="parity-py-") as py_dir:
        ts_stdout = run_ts(Path(ts_dir))
        py_stdout = run_py(Path(py_dir))

    ts_spans = parse_spans(ts_stdout)
    py_spans = parse_spans(py_stdout)
    ts_tree = tree_signature(ts_spans)
    py_tree = tree_signature(py_spans)

    if ts_tree == py_tree:
        print(f"OK - {len(ts_spans)} spans, structurally identical span tree across typescript/ and python/.")
        return 0

    print("MISMATCH between typescript/ and python/ trace span trees:", file=sys.stderr)
    print(f"  typescript/ ({len(ts_spans)} spans):\n    {ts_tree}", file=sys.stderr)
    print(f"  python/ ({len(py_spans)} spans):\n    {py_tree}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
