from multiagent_boilerplate.harness import (
    AgentRoleDef,
    AuditCorrelation,
    AuditEntry,
    Harness,
    HarnessOptions,
    HarnessToolCall,
    redact,
)
from multiagent_boilerplate.tools.registry import build_tool_registry


class CapturingSink:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class NoRuntime:
    async def spawn_subagents(self, tasks, depth):
        raise RuntimeError("n/a")

    async def write_artifact(self, kind, summary, content, created_by):
        return {}

    async def read_artifact(self, artifact_id):
        return {}

    async def save_plan(self, plan):
        return None


def _subagent_role() -> AgentRoleDef:
    return AgentRoleDef(
        role="subagent", allowed_tools=["search_web"], can_spawn=[], max_delegation_depth=0, budget={"maxToolCalls": 5}
    )


def test_redaction_deep_walks() -> None:
    out = redact(
        {"query": "hello", "apiKey": "sk-123", "nested": {"password": "p", "city": "NYC"}, "list": [{"token": "t"}]}
    )
    assert out == {
        "query": "hello",
        "apiKey": "[redacted]",
        "nested": {"password": "[redacted]", "city": "NYC"},
        "list": [{"token": "[redacted]"}],
    }


async def test_records_entry_for_successful_call() -> None:
    sink = CapturingSink()
    harness = Harness(build_tool_registry(), HarnessOptions(audit_sink=sink))
    outcome = await harness.execute(
        _subagent_role(),
        HarnessToolCall(
            idempotency_key="k1",
            tool_name="search_web",
            input={"query": "x", "apiKey": "sk-secret"},
            delegation_depth=1,
            correlation=AuditCorrelation(trace_id="tr", session_id="se", request_id="rq"),
        ),
        NoRuntime(),
    )
    assert outcome.status == "ok"
    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.tool_name == "search_web"
    assert entry.result_status == "ok"
    assert entry.trace_id == "tr"
    assert entry.params_redacted == {"query": "x", "apiKey": "[redacted]"}


async def test_records_entry_even_when_rejected() -> None:
    sink = CapturingSink()
    harness = Harness(build_tool_registry(), HarnessOptions(audit_sink=sink))
    outcome = await harness.execute(
        _subagent_role(),
        HarnessToolCall(idempotency_key="k2", tool_name="spawn_subagents", input={}, delegation_depth=0),
        NoRuntime(),
    )
    assert outcome.status == "rejected"
    assert len(sink.entries) == 1
    assert sink.entries[0].result_status == "rejected"
    assert sink.entries[0].error_type == "auth"
