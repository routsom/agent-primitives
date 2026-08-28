---
title: Profiler & cost
description: A built-in, Instruments-style dashboard for every run - gauges, token distribution, over-time charts, per-agent tracks, and a waterfall - plus real dollar cost, static or live.
---

Run your agents and get a dashboard. No orchestration framework ships this out of the box, and
you don't wire anything up: it renders from the trace spans every run already emits
([Tracing & audit](/tracing/)).

![agent-primitives profiler](/agent-primitives/profiler.png)

## What it shows

- **Gauges** - tokens used against the session budget, and **estimated dollar cost** against a
  soft cap, with green/yellow/red zones.
- **Token distribution** - a donut of where the tokens went (lead vs each subagent vs citation).
- **Over time** - cumulative tokens and cost as area charts, with the run's totals.
- **Agent tracks** - one sparkline row per agent, like a per-thread view.
- **Timeline** - the full turn → agent → model/tool call waterfall, colored by kind and status,
  click any bar to inspect its tokens, cost, timing, and attributes.

## Two modes, one template

Both runtimes read the same `dashboard/template.html`, so the profiler can't drift between
TypeScript and Python.

### Static export (default)

Every example run writes a **self-contained** `dashboard-<runId>.html` next to its artifacts and
opens it. Zero dependencies, no server, works fully offline - inline JS/CSS with the trace data
embedded. Share it, attach it to a bug report, diff two runs.

```bash
npm run example:research                       # TypeScript
uv run python -m examples.research_task        # Python
```

### Live (real time)

Opt in and the run starts a tiny local **Server-Sent Events** server (owned `node:http` /
`http.server`, no framework - the same approach as the [A2A server](/a2a/)) and opens the page
before the run. Gauges and charts fill in **as spans complete**.

```bash
npm run profile                                # TypeScript (PROFILER=live)
PROFILER=live uv run python -m examples.research_task   # Python
```

The page subscribes over SSE when served live and falls back to the embedded snapshot when
opened as a file - the same HTML either way.

## Live eval dashboard

The same dashboard renders an **Evals** section from LLM-as-judge verdicts: a radar of the
average score per rubric criterion (accuracy · completeness · source quality · process ·
disclosure), summary cards (tasks judged · average · pass rate · flagged), and a **per-task
score heatmap** with review flags. It fills row-by-row in real time as each task is judged.

![agent-primitives eval dashboard](/agent-primitives/eval-dashboard.png)

```bash
npm run eval             # writes a static eval dashboard and opens it
npm run eval:profile     # live: each task's judge scores stream in as they land
# Python: uv run python -m multiagent_boilerplate.evals.run_eval
#   live: PROFILER=live uv run python -m multiagent_boilerplate.evals.run_eval
```

The structural review flags a run derives deterministically ([notes §16a](/evals/)) show up in
the heatmap's Review column - so a run that hid a dead end or truncated is flagged even when the
judge scored it well. A run that is itself judged also shows its single verdict on its own run
dashboard.

## Dollar cost

Cost is derived deterministically from the token counts each span carries, using the editable
price table at `specs/pricing.json` (USD per 1M tokens, keyed by `provider:model`, with a
separate Anthropic prompt-cache rate). Edit it to match your contract - it's an estimate for the
profiler, not billing truth. Each `model_call` span gets a `costUsd`; the dashboard sums them.

The mock provider is priced at `$0` so offline runs cost nothing. For a realistic demo, set
`MOCK_PRICE_AS=anthropic:claude-sonnet-5` to price mock tokens at a real model's rate.

## Using it in your own code

The dashboard is just a consumer of the `Tracer`. Point it at any run:

```ts
import { writeDashboard } from "@agent-primitives/typescript";
writeDashboard(tracer.allSpans(), "run.html", { runId, tokenBudget: 250000 });
// or, live:
import { startDashboardServer } from "@agent-primitives/typescript";
const server = startDashboardServer({ tracer, meta: { runId } }); // http://localhost:8790
```

```py
from multiagent_boilerplate.tracing.dashboard import write_dashboard
write_dashboard(tracer.all_spans(), "run.html", meta={"runId": run_id, "tokenBudget": 250000})
# or, live:
from multiagent_boilerplate.tracing.dashboard_server import start_dashboard_server
server = start_dashboard_server(tracer, meta={"runId": run_id})  # http://localhost:8790
```
