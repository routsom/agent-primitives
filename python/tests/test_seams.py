from multiagent_boilerplate.harness import (
    AgentRoleDef,
    CircuitBreakerOptions,
    Harness,
    HarnessOptions,
    HarnessToolCall,
    ToolCircuitBreaker,
)
from multiagent_boilerplate.tracing.otlp import to_otlp_span
from multiagent_boilerplate.tracing.tracer import Tracer


class NoRuntime:
    async def spawn_subagents(self, tasks, depth):
        raise RuntimeError("n/a")

    async def write_artifact(self, kind, summary, content, created_by):
        return {}

    async def read_artifact(self, artifact_id):
        return {}

    async def save_plan(self, plan):
        return None


class FlakyTool:
    name = "flaky"
    description = "always raises"
    input_schema = {"type": "object"}
    exposable = False

    async def execute(self, input_, ctx):
        raise RuntimeError("503 backend down")


class EchoTool:
    name = "echo"
    description = "echoes input"
    input_schema = {"type": "object"}
    exposable = False

    async def execute(self, input_, ctx):
        return input_


def _role(tools: list[str]) -> AgentRoleDef:
    return AgentRoleDef(
        role="subagent",
        allowed_tools=tools,
        can_spawn=[],
        max_delegation_depth=0,
        budget={"maxToolCalls": 100},
    )


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = ToolCircuitBreaker(CircuitBreakerOptions(failure_threshold=3, window_ms=1000, cooldown_ms=1000))
    assert breaker.is_open("t") is False
    breaker.record_failure("t")
    breaker.record_failure("t")
    assert breaker.is_open("t") is False
    breaker.record_failure("t")
    assert breaker.is_open("t") is True


def test_circuit_breaker_half_opens_after_cooldown() -> None:
    breaker = ToolCircuitBreaker(CircuitBreakerOptions(failure_threshold=1, window_ms=1000, cooldown_ms=500))
    breaker.record_failure("t", now=0)
    assert breaker.is_open("t", now=100) is True
    assert breaker.is_open("t", now=600) is False


def test_success_resets_failures() -> None:
    breaker = ToolCircuitBreaker(CircuitBreakerOptions(failure_threshold=2, window_ms=1000, cooldown_ms=1000))
    breaker.record_failure("t")
    breaker.record_success("t")
    breaker.record_failure("t")
    assert breaker.is_open("t") is False


async def test_harness_short_circuits_open_tool() -> None:
    breaker = CircuitBreakerOptions(failure_threshold=2, window_ms=10_000, cooldown_ms=10_000)
    harness = Harness([FlakyTool()], HarnessOptions(circuit_breaker=breaker))
    role = _role(["flaky"])
    await harness.execute(role, HarnessToolCall("a", "flaky", {}, 0), NoRuntime())
    await harness.execute(role, HarnessToolCall("b", "flaky", {}, 0), NoRuntime())
    outcome = await harness.execute(role, HarnessToolCall("c", "flaky", {}, 0), NoRuntime())
    assert outcome.status == "rejected"
    assert outcome.error is not None
    assert "circuit is open" in outcome.error.message


async def test_sanitize_seam_applied_to_tool_output() -> None:
    def wrap(_boundary: str, content: object) -> dict:
        return {"sanitized": True, "original": content}

    harness = Harness([EchoTool()], HarnessOptions(sanitize=wrap))
    role = _role(["echo"])
    outcome = await harness.execute(role, HarnessToolCall("x", "echo", {"hi": 1}, 0), NoRuntime())
    assert outcome.status == "ok"
    assert outcome.output == {"sanitized": True, "original": {"hi": 1}}


def test_otlp_span_mapping() -> None:
    tracer = Tracer(on_span_end=lambda _s: None)
    span = tracer.start_span("model_call", "lead turn 0", agent_role="lead", delegation_depth=0)
    tracer.end_span(span, "ok", token_usage={"inputTokens": 10, "outputTokens": 5})
    otlp = to_otlp_span(span)
    assert otlp["name"] == "lead turn 0"
    assert otlp["spanId"] == span.span_id
    assert otlp["status"] == {"code": 1}
    assert isinstance(otlp["attributes"], list)
