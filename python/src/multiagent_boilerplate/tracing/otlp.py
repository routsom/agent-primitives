"""Maps a TraceSpan to the OpenTelemetry OTLP/JSON span shape. The span is already
OTel-compatible by construction (specs/schemas/trace-span.schema.json) - this just renames
fields and encodes attributes into OTLP's key/value form so the output drops straight into any
OTLP/HTTP collector.

This is the *seam*: it produces the wire shape. Shipping the actual network exporter (gRPC or
HTTP to a collector) is left to you deliberately - it depends on your collector endpoint and
auth, and pulling in an OTLP transport would be exactly the kind of heavyweight dependency this
boilerplate avoids. See docs/extending.md.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .tracer import TraceSpan


def to_otlp_span(span: TraceSpan) -> dict:
    raw_attributes: dict[str, Any] = {
        "agent.role": span.agent_role,
        "agent.delegation_depth": span.delegation_depth,
        "span.app_kind": span.kind,
    }
    if span.token_usage:
        raw_attributes.update(span.token_usage)
    if span.attributes:
        raw_attributes.update(span.attributes)

    attributes = [
        {"key": key, "value": _to_any_value(value)} for key, value in raw_attributes.items() if value is not None
    ]

    otlp: dict[str, Any] = {
        "traceId": span.trace_id,
        "spanId": span.span_id,
        "name": span.name,
        "startTimeUnixNano": _to_unix_nano(span.started_at),
        "kind": 1,  # SPAN_KIND_INTERNAL
        "status": {"code": 2 if span.status == "error" else (0 if span.status == "partial" else 1)},
        "attributes": attributes,
    }
    if span.parent_span_id:
        otlp["parentSpanId"] = span.parent_span_id
    if span.ended_at:
        otlp["endTimeUnixNano"] = _to_unix_nano(span.ended_at)
    return otlp


def otlp_console_exporter(span: TraceSpan) -> None:
    """A ready-to-use Tracer sink that prints each span in OTLP/JSON form."""
    print(f"[otlp] {json.dumps(to_otlp_span(span))}")


def _to_any_value(value: Any) -> dict:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": value}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def _to_unix_nano(iso: str) -> str:
    return f"{int(datetime.fromisoformat(iso).timestamp() * 1000)}000000"
