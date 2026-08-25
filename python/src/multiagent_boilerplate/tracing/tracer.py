"""Nested span tree: turn -> agent -> model/tool call (notes section 11). Default exporter
prints to stdout; swap `on_span_end` for an OpenTelemetry exporter in production - the span
shape (specs/schemas/trace-span.schema.json) is already OTel-compatible."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from ..harness.validate import validate_trace_span

SpanKind = Literal["turn", "agent", "model_call", "tool_call", "a2a_call"]
SpanStatus = Literal["ok", "error", "partial"]


@dataclass
class TraceSpan:
    span_id: str
    trace_id: str
    parent_span_id: str | None
    kind: SpanKind
    name: str
    agent_role: str | None
    delegation_depth: int
    started_at: str
    status: SpanStatus = "ok"
    ended_at: str | None = None
    token_usage: dict | None = None
    attributes: dict | None = None

    def to_schema_dict(self) -> dict:
        data = {
            "spanId": self.span_id,
            "traceId": self.trace_id,
            "parentSpanId": self.parent_span_id,
            "kind": self.kind,
            "name": self.name,
            "agentRole": self.agent_role,
            "delegationDepth": self.delegation_depth,
            "startedAt": self.started_at,
            "status": self.status,
        }
        if self.ended_at is not None:
            data["endedAt"] = self.ended_at
        if self.token_usage is not None:
            data["tokenUsage"] = self.token_usage
        if self.attributes is not None:
            data["attributes"] = self.attributes
        return data


def _default_on_span_end(span: TraceSpan) -> None:
    print(f"[trace] {json.dumps(span.to_schema_dict())}")


@dataclass
class Tracer:
    on_span_end: Callable[[TraceSpan], None] = field(default=_default_on_span_end)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _spans: list[TraceSpan] = field(default_factory=list, init=False)

    def start_span(
        self,
        kind: SpanKind,
        name: str,
        parent_span_id: str | None = None,
        agent_role: str | None = None,
        delegation_depth: int = 0,
    ) -> TraceSpan:
        span = TraceSpan(
            span_id=str(uuid.uuid4()),
            trace_id=self.trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            name=name,
            agent_role=agent_role,
            delegation_depth=delegation_depth,
            started_at=datetime.now(UTC).isoformat(),
        )
        self._spans.append(span)
        return span

    def end_span(
        self,
        span: TraceSpan,
        status: SpanStatus = "ok",
        token_usage: dict | None = None,
        attributes: dict | None = None,
    ) -> None:
        span.ended_at = datetime.now(UTC).isoformat()
        span.status = status
        if token_usage is not None:
            span.token_usage = token_usage
        if attributes is not None:
            span.attributes = attributes
        validate_trace_span(span.to_schema_dict())
        self.on_span_end(span)

    def all_spans(self) -> list[TraceSpan]:
        return list(self._spans)
