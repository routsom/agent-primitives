# agent-primitives (Python runtime)

Python reference implementation of the orchestrator-worker multi-agent architecture described
in [`../reference/multi-agent-architecture-notes.md`](../reference/multi-agent-architecture-notes.md).
Mirrors [`../typescript/`](../typescript/) layer for layer, reading the same
[`../specs/`](../specs/) contracts. See the repository root [`README.md`](../README.md) and
[`DESIGN.md`](../DESIGN.md) for the full picture.

## Quickstart

```bash
uv sync
cp .env.example .env   # optional: add ANTHROPIC_API_KEY to use a real model
uv run python -m examples.research_task
```

## Commands

```bash
uv sync                                    # install deps
uv run ruff check .                        # lint
uv run pytest                              # tests
uv run python -m examples.research_task    # full orchestrator-worker flow
uv run python -m examples.single_agent     # single-agent baseline
uv run python -m multiagent_boilerplate.evals.run_eval   # eval seed set
```

Defaults to a mock provider requiring no API keys, same as the TypeScript runtime.
