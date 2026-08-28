"""Writes the self-contained, zero-dependency profiler dashboard for a run by injecting its
trace spans into the shared dashboard/template.html. Both runtimes read the same template, so
the dashboard can't drift between TypeScript and Python. Mirrors typescript/src/tracing/dashboard.ts."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from ..harness.schemas import REPO_ROOT
from .tracer import TraceSpan

PAYLOAD_SENTINEL = "%%AGENT_PRIMITIVES_PAYLOAD%%"


def read_template() -> str:
    return (REPO_ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")


def render_dashboard(spans: list[TraceSpan], meta: dict | None = None, evals: list[dict] | None = None) -> str:
    """Builds the full dashboard HTML by injecting the run payload at the single sentinel.
    `evals` is a list of LLM-judge verdict dicts (taskId, scores, flagForHumanReview,
    structuralFlags), rendered in the dashboard's Evals section."""
    payload = {"meta": meta or {}, "spans": [s.to_schema_dict() for s in spans], "evals": evals or []}
    # Escape `<` so a stray "</script>" in span data can't break out of the tag.
    json_text = json.dumps(payload).replace("<", "\\u003c")
    return read_template().replace(PAYLOAD_SENTINEL, json_text)


def write_dashboard(
    spans: list[TraceSpan], out_file: str, meta: dict | None = None, evals: list[dict] | None = None
) -> str:
    path = Path(out_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(spans, meta, evals), encoding="utf-8")
    return str(path)


def maybe_open(target: str) -> None:
    """Opens a file path or URL in the default browser, unless in CI or stdout isn't a TTY.
    Best-effort and non-fatal."""
    if os.environ.get("CI") or os.environ.get("NO_OPEN") or not sys.stdout.isatty():
        return
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001 - opening is a convenience, never a hard failure
        pass
