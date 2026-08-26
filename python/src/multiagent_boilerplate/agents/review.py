"""Structural checks on the trace that just completed (notes section 16a: 'what actually sets
needs_review: true - not the LLM judge'). Every check reads a field the run already produced;
none costs an extra inference. The judge, if run, is triggered *by* these flags rather than
being what sets them - so the expensive path only fires on runs a cheap check already flagged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..harness.errors import ToolError


@dataclass
class ReviewSignals:
    status: Literal["ok", "partial", "error"]
    unrecovered_errors: list[ToolError]
    final_text: str
    # Stop reason of the final model call, if the loop ended on the model (not on a cap).
    last_stop_reason: Literal["end_turn", "tool_use", "max_tokens"] | None = None


def derive_review_flags(signals: ReviewSignals) -> list[str]:
    flags: list[str] = []

    if signals.status == "partial":
        flags.append("partial_completion")
    if signals.status == "error":
        flags.append("errored")

    # One flag per distinct unrecovered error type (auth failures are always worth a look).
    for error_type in dict.fromkeys(e.type for e in signals.unrecovered_errors):
        flags.append(f"unrecovered_tool_error:{error_type}")

    if signals.last_stop_reason == "max_tokens":
        flags.append("max_tokens_truncation")

    # An "ok" run that produced almost no text is suspicious - the model may have bailed.
    if signals.status == "ok" and len(signals.final_text.strip()) < 20:
        flags.append("empty_response")

    return flags
