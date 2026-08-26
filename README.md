# agent-primitives

A framework-free, multi-LLM boilerplate for building production multi-agent systems.
Clone it, add an API key, and you have a running orchestrator-worker system — lead agent,
parallel subagents, tool harness, MCP, A2A, tracing, evals — in **TypeScript** and **Python**,
side by side, sharing one set of contracts.

[![CI - TypeScript](https://github.com/routsom/agent-primitives/actions/workflows/ci-ts.yml/badge.svg)](.github/workflows/ci-ts.yml)
[![CI - Python](https://github.com/routsom/agent-primitives/actions/workflows/ci-py.yml/badge.svg)](.github/workflows/ci-py.yml)
[![Docs](https://github.com/routsom/agent-primitives/actions/workflows/docs.yml/badge.svg)](.github/workflows/docs.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Why this exists

Most multi-agent starting points are either a thin wrapper around one vendor's SDK, or a
heavyweight framework that owns your control flow. This is neither:

- **No orchestration framework.** LangGraph, CrewAI, AutoGen, etc. are not dependencies here
  — the agent loop, harness, and orchestration are plain, owned code. See
  [`DESIGN.md`](DESIGN.md#why-no-orchestration-framework) for why.
- **Multi-LLM by design.** Thin adapters over each vendor's *official* SDK
  (Anthropic, OpenAI, Gemini), not a third-party routing layer.
- **MCP and A2A wired in**, not bolted on — mount external MCP servers as tools, expose this
  system's agents over Agent-to-Agent (with bearer-token auth and rate limiting at the edge).
- **Guarantees, not hopes** — deterministic harness code for error classification, session
  token budgets, provider retry/timeout/fallback, per-tool circuit breaking, a 100% audit log,
  and derived `needs_review` flags. The model owns judgment; the harness owns guarantees.
- **Grounded in a written architecture**, not ad hoc: every module traces back to a specific
  section of [`reference/multi-agent-architecture-notes.md`](reference/multi-agent-architecture-notes.md).
  See [`DESIGN.md`](DESIGN.md) for the map.
- **Built for agentic coding from day one** — `CLAUDE.md`, hooks, subagent role definitions,
  and slash commands are first-class, not an afterthought bolted on for one tool.

## Architecture at a glance

```mermaid
flowchart TB
    User([User / A2A caller]) --> Edge[Auth + rate limit]
    Edge --> Lead[Lead agent]
    Lead -->|spawn_subagents| Harness
    subgraph Harness["Harness — guarantees, every tool call routes through"]
        Scope[scope] --> Breaker[circuit breaker] --> Idem[idempotency] --> Budgets[budgets] --> Classify[classify / sanitize]
    end
    Harness --> SubA[Subagent A] & SubB[Subagent B]
    Lead & SubA & SubB --> Resilience[[Resilience: timeout · retry · fallback]] --> LLMs[(Anthropic · OpenAI · Gemini)]
    SubA & SubB --> Artifacts[(Artifact store)] -->|refs| Lead
    Lead --> Citation[Citation agent] --> User
    Harness -.->|100%| Audit[(Audit log)]
    Lead & SubA & SubB -.-> Trace[(Trace spans)]
```

Full diagrams (sequence + end-to-end flow chart) are in
[`reference/multi-agent-system-diagrams.md`](reference/multi-agent-system-diagrams.md) and the
[docs site](https://routsom.github.io/agent-primitives/).

## Quickstart

### TypeScript

```bash
cd typescript
npm install
cp .env.example .env        # optional: add ANTHROPIC_API_KEY to use a real model
npm run example:research    # runs the full orchestrator-worker flow
```

### Python

```bash
cd python
uv sync
cp .env.example .env        # optional: add ANTHROPIC_API_KEY to use a real model
uv run python -m examples.research_task
```

Both examples default to a **mock provider** — no API key required to see the system run.

## What's in the box

| Layer | Purpose |
|---|---|
| `providers/` | `ChatModel` adapters over Anthropic / OpenAI / Gemini official SDKs + mock; resilience decorator (timeout/retry/fallback) |
| `harness/` | Guarantees: scoping, idempotency, error classification, budgets, circuit breaker, rate limiting, audit log, boundary guardrail |
| `tools/`, `mcp/` | Typed tool contract with a classified error envelope; MCP client and server |
| `agents/` | Lead agent, subagents, citation agent, deterministic `needs_review` derivation |
| `a2a/` | Agent-to-Agent server (auth + rate limit) and client |
| `memory/`, `artifacts/` | Plan and artifact stores behind pluggable `PlanStore` / `ArtifactStore` seams |
| `orchestrator/` | Synchronous fan-out/fan-in; depth + retry breakers; session token budget; partial-completion policy |
| `tracing/` | Nested spans (turn → agent → call), OTLP export seam, separate 100% audit stream |
| `evals/` | LLM-as-judge rubric; structural review flags trigger the judge |

Both `typescript/` and `python/` implement every layer, reading shared contracts from
`specs/`.

## Individual and enterprise use

- **Individual / small team:** clone, run the mock-provider example, swap in one provider key,
  ship. No account, no platform, no lock-in.
- **Enterprise:** the harness's least-privilege scoping, two-level kill switch, rainbow
  deployment guidance, and OpenTelemetry-compatible tracing (see
  [`DESIGN.md`](DESIGN.md#deployment-posture)) are designed to sit inside existing
  infrastructure and observability stacks rather than replace them.

## Documentation

Full docs (architecture, provider setup, MCP, A2A, harness, tracing, evals, deployment,
Claude Code integration, security): **[docs site](https://routsom.github.io/agent-primitives/)**
— built from [`docs/`](docs/) via Starlight.

## Repository layout

```
specs/          language-agnostic contracts: schemas, prompts, agent roles, MCP/A2A descriptors
typescript/     full runtime, independent build/test/CI
python/         full runtime, independent build/test/CI
reference/      the architecture notes this boilerplate implements
docs/           Starlight documentation site
deploy/         reference Dockerfiles for each runtime
scripts/        check_parity.py - cross-language behavioral parity check
.claude/        Claude Code hooks, subagent roles, slash commands
.github/        CI/CD workflows, issue/PR templates
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Read the "no orchestration framework" ground rule
before proposing a new dependency.

## License

[MIT](LICENSE)
