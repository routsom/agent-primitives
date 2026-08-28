import os
from datetime import UTC, datetime

from multiagent_boilerplate.cost.pricing import compute_cost_usd, price_key
from multiagent_boilerplate.providers.types import TokenUsage
from multiagent_boilerplate.tracing.dashboard import render_dashboard
from multiagent_boilerplate.tracing.tracer import TraceSpan


def test_prices_known_model() -> None:
    cost = compute_cost_usd("anthropic", "claude-sonnet-5", TokenUsage(input_tokens=1000, output_tokens=500))
    assert abs(cost - 0.0105) < 1e-6


def test_cached_rate_applied() -> None:
    cost = compute_cost_usd(
        "anthropic", "claude-sonnet-5", TokenUsage(input_tokens=1000, output_tokens=0, cached_input_tokens=800)
    )
    assert abs(cost - (200 * 3 + 800 * 0.3) / 1_000_000) < 1e-9


def test_unknown_model_is_zero() -> None:
    assert compute_cost_usd("acme", "unknown", TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)) == 0


def test_mock_zero_by_default() -> None:
    os.environ.pop("MOCK_PRICE_AS", None)
    assert compute_cost_usd("mock", "mock-deterministic-1", TokenUsage(input_tokens=1000, output_tokens=1000)) == 0


def test_mock_priced_when_env_set() -> None:
    os.environ["MOCK_PRICE_AS"] = "anthropic:claude-sonnet-5"
    try:
        cost = compute_cost_usd("mock", "mock-deterministic-1", TokenUsage(input_tokens=1000, output_tokens=0))
        assert abs(cost - 0.003) < 1e-6
    finally:
        os.environ.pop("MOCK_PRICE_AS", None)


def test_price_key() -> None:
    assert price_key("openai", "gpt-5") == "openai:gpt-5"


def _span() -> TraceSpan:
    return TraceSpan(
        span_id="s1",
        trace_id="trace-abc",
        parent_span_id=None,
        kind="turn",
        name="research-task",
        agent_role=None,
        delegation_depth=0,
        started_at=datetime.now(UTC).isoformat(),
        ended_at=datetime.now(UTC).isoformat(),
        status="ok",
    )


def test_dashboard_injects_payload() -> None:
    html = render_dashboard([_span()], meta={"runId": "trace-abc", "tokenBudget": 250000})
    assert "%%AGENT_PRIMITIVES_PAYLOAD%%" not in html
    assert '"spans"' in html
    assert "trace-abc" in html
    assert '"tokenBudget": 250000' in html


def test_dashboard_escapes_script_break() -> None:
    evil = _span()
    evil.name = "</script><script>alert(1)</script>"
    html = render_dashboard([evil], meta={})
    data_part = html.split("ap-payload", 1)[1][:2000]
    assert "</script><script>alert" not in data_part
    assert "\\u003c" in html
