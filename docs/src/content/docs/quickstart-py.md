---
title: "Quickstart: Python"
description: Clone, sync, and run the Python runtime end to end in under a minute.
---

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages the Python interpreter and virtualenv for you - no separate Python install needed)

## Install

```bash
git clone https://github.com/routsom/agent-primitives.git
cd agent-primitives/python
uv sync
```

`uv sync` provisions Python 3.12+ automatically per `.python-version` if you don't already have
a matching interpreter.

## Run the full orchestrator-worker flow

No API key required - this uses the deterministic mock provider by default.

```bash
uv run python -m examples.research_task
```

You'll see the same shape as the TypeScript run: a lead agent decomposes the query, spawns two
parallel subagents, each writes an artifact, and a citation agent synthesizes the final answer -
with a full nested trace printed as it runs. The two runtimes are built to produce structurally
equivalent traces from the same shared `specs/`.

## Run the single-agent baseline

```bash
uv run python -m examples.single_agent
```

## Use a real model

Copy `.env.example` to `.env` and set a provider key:

```bash
cp .env.example .env
# then edit .env:
# ANTHROPIC_API_KEY=sk-ant-...
# DEFAULT_PROVIDER=anthropic
```

Supported logical providers: `anthropic`, `openai`, `google`, `mock` (default). See
[Providers](/providers/) for how the adapter layer resolves this.

## Everything else

```bash
uv run ruff check .                                       # lint
uv run ruff format --check .                               # format check
uv run pytest -q                                            # tests
uv run python -m multiagent_boilerplate.evals.run_eval      # LLM-judge eval seed set, see /evals/
```

## Where to go next

- [Architecture](/architecture/) for the module map and the reasoning behind each layer.
- [Harness](/harness/) for how tool calls are validated, scoped, and budget-capped.
- [Claude Code integration](/claude-code/) if you're extending this repo with Claude Code.
