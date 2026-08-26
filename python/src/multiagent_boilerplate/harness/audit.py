"""The audit log is NOT the eval trace (notes section 12, 22). Two separate streams that share
correlation IDs but have different retention, access control, and completeness guarantees:

  - Audit (this file): 100% of tool calls, PII-redacted params, for compliance and forensics.
           Queryable by session or customer. An independent record of what the system actually
           did - not reliant on what the model claims happened.
  - Trace (tracing/tracer.py): spans for quality measurement, sampled, async.

Every tool call routes through Harness.execute, the single 100%-coverage chokepoint where these
entries are emitted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class AuditCorrelation:
    trace_id: str
    session_id: str
    request_id: str


@dataclass
class AuditEntry:
    timestamp: str
    trace_id: str
    session_id: str
    request_id: str
    agent_role: str
    tool_name: str
    idempotency_key: str
    delegation_depth: int
    params_redacted: dict
    result_status: str
    error_type: str | None = None

    def to_dict(self) -> dict:
        data = {
            "timestamp": self.timestamp,
            "traceId": self.trace_id,
            "sessionId": self.session_id,
            "requestId": self.request_id,
            "agentRole": self.agent_role,
            "toolName": self.tool_name,
            "idempotencyKey": self.idempotency_key,
            "delegationDepth": self.delegation_depth,
            "paramsRedacted": self.params_redacted,
            "resultStatus": self.result_status,
        }
        if self.error_type is not None:
            data["errorType"] = self.error_type
        return data


@runtime_checkable
class AuditSink(Protocol):
    def record(self, entry: AuditEntry) -> None: ...


class NoopAuditSink:
    """Silent default - audit is opt-in for the boilerplate. Wire a real sink in production."""

    def record(self, entry: AuditEntry) -> None:
        return None


class ConsoleAuditSink:
    def record(self, entry: AuditEntry) -> None:
        print(f"[audit] {json.dumps(entry.to_dict())}")


class JsonlAuditSink:
    """Appends one JSON line per tool call - the shape any log pipeline ingests."""

    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: AuditEntry) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict()) + "\n")


_SENSITIVE_KEY = re.compile(
    r"(token|password|secret|api[_-]?key|authorization|ssn|card|cvv|email|amount|balance)", re.I
)


def redact(value: object, key_hint: str = "") -> object:
    """Redacts sensitive values before they reach the audit log, by key name (notes section 22:
    'PII-redacted at the point of logging'). Deterministic - never an LLM call on the logging
    path. Deep-walks dicts/lists."""
    if _SENSITIVE_KEY.search(key_hint):
        return "[redacted]"
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items()}
    return value


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
