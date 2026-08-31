"""Per-run cost ledger. RunBudget caps token *count*; the profiler shows a live dollar gauge;
this is the after-the-fact accounting in between - it turns the cost_usd every model_call span
already carries into a total plus a breakdown by model and by agent role, so "what did this run
cost, and where?" is one function call. It reads the trace the run already emitted, so it adds no
instrumentation and no extra model calls (notes section 8, 11). Mirrors typescript/src/cost/ledger.ts."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..tracing.tracer import TraceSpan


@dataclass
class CostLine:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class CostSummary:
    total: CostLine = field(default_factory=CostLine)
    by_model: dict[str, CostLine] = field(default_factory=dict)
    by_agent: dict[str, CostLine] = field(default_factory=dict)


def _add(line: CostLine, span: TraceSpan) -> None:
    usage = span.token_usage or {}
    line.calls += 1
    line.input_tokens += usage.get("inputTokens", 0)
    line.output_tokens += usage.get("outputTokens", 0)
    line.cost_usd += span.cost_usd or 0.0


def summarize_cost(spans: list[TraceSpan]) -> CostSummary:
    """Reduce a run's spans to a cost summary. Only `model_call` spans carry spend."""
    summary = CostSummary()
    for span in spans:
        if span.kind != "model_call":
            continue
        model = (span.attributes or {}).get("model", "unknown")
        agent = span.agent_role or "unknown"
        _add(summary.total, span)
        _add(summary.by_model.setdefault(model, CostLine()), span)
        _add(summary.by_agent.setdefault(agent, CostLine()), span)
    return summary


def format_cost_summary(summary: CostSummary) -> str:
    """A compact, human-readable rendering of a cost summary for a CLI or a log line."""

    def line(label: str, ln: CostLine) -> str:
        tok = ln.input_tokens + ln.output_tokens
        return f"  {label:<24} {ln.calls:>3} calls  {tok:>8} tok  ${ln.cost_usd:.6f}"

    rows = [f"Run cost: ${summary.total.cost_usd:.6f} over {summary.total.calls} model call(s)", "by model:"]
    rows += [line(model, ln) for model, ln in summary.by_model.items()]
    rows.append("by agent:")
    rows += [line(agent, ln) for agent, ln in summary.by_agent.items()]
    return "\n".join(rows)
