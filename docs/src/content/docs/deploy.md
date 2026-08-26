---
title: Deployment
description: Dockerfiles, rainbow deployment, durable execution, and the two-level kill switch.
---

:::caution
The Dockerfiles below mirror the exact local commands used throughout these docs
(`npm ci && npm run build`, `uv sync --locked`) and were exercised as plain Node/`uv` processes
during development of this boilerplate, but building the container images themselves hasn't
been verified in every environment. Run `docker build` yourself before relying on them in
production.
:::

## Reference Dockerfiles

`deploy/Dockerfile.typescript` and `deploy/Dockerfile.python` each build a container that runs
a minimal [A2A](/a2a/) server exposing the subagent role, backed by a real `Orchestrator`
(harness, artifact store, plan memory) - not a toy. Build from the **repository root**, not the
runtime subdirectory, since `specs/` and `reference/` are read at runtime and must ship
alongside the compiled code:

```bash
docker build -f deploy/Dockerfile.typescript -t agent-primitives-ts .
docker run -p 8787:8787 -e ANTHROPIC_API_KEY agent-primitives-ts

docker build -f deploy/Dockerfile.python -t agent-primitives-py .
docker run -p 8787:8787 -e ANTHROPIC_API_KEY agent-primitives-py
```

Both default entrypoints (`typescript/src/server.ts`, `python/src/multiagent_boilerplate/server.py`)
are intentionally minimal - they expose the *subagent* role over A2A as a working example.
Wrap `runLeadAgent` / `run_lead_agent` in your own HTTP handler alongside it if you need a
user-facing API; the orchestrator wiring pattern is identical.

## Rainbow deployments, not instant cutover

Multi-agent systems are long-running, stateful webs of prompts, tools, and execution logic
running almost continuously - a version change can land while agents are mid-execution.
Gradually shift traffic from the old version to the new one while both run simultaneously,
rather than switching all at once (`reference/multi-agent-architecture-notes.md` section 12).
This is the canary rollout pattern, now a necessity rather than an optimization, because of
statefulness.

## Durable execution and resumability

Agents must be able to resume from where they were when an error occurred, not restart from
scratch - restarts are expensive, frustrating, and risk duplicate side effects if any step
wasn't idempotent. The [harness's](/harness/) idempotency-key handling is the foundation this
needs; the plan-memory persistence (`memory/`, saved *before* spawning subagents) is what lets a
restarted lead agent recover its strategy rather than starting over blind.

## Combine model adaptability with deterministic safeguards

Letting an agent itself adapt when a tool fails (informing it and letting it reroute) works
well, but pair that adaptability with deterministic safeguards underneath - the same
defense-in-depth principle applied at the scale of a whole multi-step run. This is already in
place: **provider resilience** (timeout/retry/fallback for model-down), the **per-tool circuit
breaker** (for tool-backend-down), the **session token ceiling**, and error classification that
decides retryability structurally. See [Reliability & guarantees](/reliability/) for all of them.

## Kill switch, two levels

Pause the entire swarm, or pause just one agent type (e.g. the subagent role) without taking
down the whole system. A single global switch is too blunt once multiple independently-versioned
agent types exist. Neither runtime ships a built-in kill-switch mechanism (that's inherently
tied to your specific deployment infrastructure), but the two levels map directly onto this
codebase's structure: swarm-level = stop routing to the [orchestrator](/architecture/), agent-
type-level = reject at the [harness's](/harness/) scope check for one specific role.
