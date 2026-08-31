"""Per-run cost ledger: total spend plus per-model and per-agent breakdown, from trace spans."""

from __future__ import annotations

from multiagent_boilerplate.cost.ledger import format_cost_summary, summarize_cost
from multiagent_boilerplate.tracing.tracer import TraceSpan


def _model_call(agent: str, model: str, in_tok: int, out_tok: int, cost: float) -> TraceSpan:
    return TraceSpan(
        span_id="s",
        trace_id="t",
        parent_span_id=None,
        kind="model_call",
        name=f"{agent} turn 0",
        agent_role=agent,
        delegation_depth=0,
        started_at="2026-01-01T00:00:00Z",
        status="ok",
        token_usage={"inputTokens": in_tok, "outputTokens": out_tok},
        cost_usd=cost,
        attributes={"model": model},
    )


def test_totals_and_breakdown_over_model_call_spans_only() -> None:
    spans = [
        _model_call("lead", "anthropic:claude-opus-4-8", 100, 50, 0.01),
        _model_call("subagent", "anthropic:claude-sonnet-5", 200, 80, 0.004),
        _model_call("subagent", "anthropic:claude-sonnet-5", 300, 20, 0.006),
    ]
    # A non-model span carries no spend and must be ignored.
    tool_span = _model_call("lead", "x", 999, 999, 999.0)
    tool_span.kind = "tool_call"
    spans.append(tool_span)

    summary = summarize_cost(spans)
    assert summary.total.calls == 3
    assert summary.total.input_tokens == 600
    assert summary.total.output_tokens == 150
    assert abs(summary.total.cost_usd - 0.02) < 1e-6

    assert summary.by_model["anthropic:claude-sonnet-5"].calls == 2
    assert abs(summary.by_model["anthropic:claude-sonnet-5"].cost_usd - 0.01) < 1e-6
    assert abs(summary.by_agent["subagent"].cost_usd - 0.01) < 1e-6
    assert summary.by_agent["lead"].calls == 1


def test_renders_readable_summary() -> None:
    summary = summarize_cost([_model_call("lead", "anthropic:claude-opus-4-8", 100, 50, 0.01)])
    text = format_cost_summary(summary)
    assert "Run cost:" in text
    assert "anthropic:claude-opus-4-8" in text
    assert "lead" in text
