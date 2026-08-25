# CLAUDE.md

Guidance for Claude Code (and any other coding agent) working in this repository.

## What this repo is

A framework-free, multi-LLM boilerplate for building production multi-agent systems, with
two independent reference implementations (`typescript/`, `python/`) that share one set of
contracts (`specs/`). See `DESIGN.md` for the architecture and `reference/` for the source
notes it implements.

## Source of truth: edit `specs/`, not the runtimes' copies

`specs/schemas`, `specs/prompts`, and `specs/agents` are language-agnostic and consumed by
**both** runtimes. If you change agent behavior, tool contracts, or prompts, edit `specs/`
first, then update both `typescript/` and `python/` to match. Never let the two runtimes'
prompts or schemas drift independently — `python3 scripts/check_parity.py` runs the
research-task example in both runtimes against the mock provider and diffs their trace span
trees; run it after cross-cutting changes.

## Layer order (both runtimes follow this)

`providers → harness → tools/mcp → agents → orchestrator → tracing → a2a → evals`. Each
layer only depends on the ones before it. When adding a feature, place it in the
narrowest layer that needs it rather than reaching across.

## The single-agent-first principle

This codebase implements an orchestrator-worker multi-agent system, but multi-agent is an
escalation, not a default (`reference/multi-agent-architecture-notes.md` §1). When extending
`examples/`, keep `examples/single-agent` as the baseline comparison — don't delete it, and
don't reach for more subagents to solve something one well-prompted agent handles.

## Cost and safety discipline

Hard caps (subagent count, tool-call budget, delegation depth) live in the harness config,
not scattered through agent prompts. If you add a new spawn path, it must route through the
harness so the existing caps apply — no agent-to-agent shortcut around it.

## Commands

TypeScript (`typescript/`):
```
npm install
npm run typecheck
npm run lint
npm test
npm run example:research     # runs examples/research-task
npm run example:single-agent
npm run eval                  # LLM-judge eval seed set
npm run build && npm start    # compiled A2A server (see deploy/Dockerfile.typescript)
```

Python (`python/`):
```
uv sync
uv run ruff check .
uv run pytest
uv run python -m examples.research_task
uv run python -m examples.single_agent
uv run python -m multiagent_boilerplate.evals.run_eval
uv run python -m multiagent_boilerplate.server   # A2A server (see deploy/Dockerfile.python)
```

Docs (`docs/`):
```
npm install
npm run dev      # local preview
npm run build    # static build, same as CI
```

Cross-runtime, from the repo root:
```
python3 scripts/check_parity.py   # required after any specs/ change
```

Both runtimes default to a **mock provider** requiring no API keys — CI and first-run both
use it. Set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` in `.env` (see
`.env.example` in each runtime) to run against a real model.

## Claude Code integration in this repo

- `.claude/agents/` mirrors the role definitions in `specs/agents` — if you add or change an
  agent role, update both.
- `.claude/settings.json` runs lint/typecheck/test as hooks on file edits and session stop.
  Don't bypass them; fix what they flag.
- `.claude/commands/` has `/run-task`, `/eval`, `/trace` for exercising the runtime from
  inside a coding session.

## What not to do

- Don't add an orchestration framework (LangChain/LangGraph/CrewAI/AutoGen/etc.) as a
  dependency in either runtime — the point of this boilerplate is owning the agent loop.
- Don't add a new LLM provider by depending on a routing library — write a thin adapter over
  the vendor's official SDK in `providers/`, matching the existing `ChatModel` interface.
- Don't dump raw subagent output back to the lead agent — distill findings and return an
  artifact reference (`reference/multi-agent-architecture-notes.md` §4).
