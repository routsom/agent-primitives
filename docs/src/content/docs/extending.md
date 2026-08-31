---
title: Extending it
description: The seams this boilerplate exposes on purpose, and the things it deliberately does NOT build - so extending it never means forking a framework.
---

This boilerplate ships **primitives with typed seams**, not a platform. The line it holds:

> A primitive gives you a typed seam and a deterministic guarantee, and lets *you* wire the
> control flow. A framework owns the control-flow loop and makes you plug into *its* opinions.

Everything below is either a seam that already exists in the code (swap one implementation for
another) or a deliberate non-goal (here's the seam you'd attach, here's why we didn't bundle
the machinery). If you find yourself adding an orchestration engine, a control plane, or a
policy DSL, stop - that's the framework cliff.

## Seams that already exist (swap an implementation)

These are real interfaces in the runtime today. Provide your own implementation and pass it in;
nothing above the seam changes.

| Seam | Interface | Default | Swap for |
|---|---|---|---|
| **LLM provider** | `ChatModel` (`providers/`) | Anthropic / OpenAI / Gemini / mock | Any vendor - write a thin adapter over its official SDK |
| **Provider resilience** | `ResilientChatModel` | timeout + retry + (no) fallback | Add fallback providers/regions for model-down failover |
| **Record / replay** | `ReplayChatModel` (`providers/`) | records to a cassette, replays offline | Point at a cassette dir; use `replay` mode in CI for zero-token, deterministic runs |
| **Human-in-the-loop** | `ApprovalProvider` (`harness/`) | `AutoApprove` (gates nothing) | `ToolApprovalGate` + your resolver (a UI queue, a policy check) |
| **Context compaction** | `Compactor` (`agents/`) | off (no compaction) | `SummarizingCompactor` with an LLM or model-free `summarize` |
| **Artifact storage** | `ArtifactStore` (`artifacts/`) | local filesystem | S3, GCS, a database - implement `write`/`read` |
| **Plan storage** | `PlanStore` (`memory/`) | local filesystem | A durable job store (Postgres, DynamoDB) |
| **Checkpoint storage** | `CheckpointStore` (`orchestrator/`) | local filesystem | A database or workflow engine (Temporal) for resumable runs |
| **Audit log** | `AuditSink` (`harness/`) | `NoopAuditSink` (silent) | `ConsoleAuditSink`, `JsonlAuditSink`, or your log pipeline |
| **Trace export** | `Tracer` `onSpanEnd` sink + `toOtlpSpan` | console JSON | `otlpConsoleExporter`, then wire the OTLP wire-shape to your collector |
| **Rate limiting** | `SlidingWindowRateLimiter` | in-memory, single process | Back the same interface with Redis for multi-instance |
| **Boundary guardrail** | `Sanitize` hook (`harness/`) | identity (no-op) | Strip injected instructions, scrub PII, enforce allowed shapes |
| **Tool circuit breaker** | `ToolCircuitBreaker` | in-memory per-process | Shared state across instances via Redis if you run many replicas |

Each is passed via the `Harness` / `Orchestrator` options - see the [Harness](/harness/) and
[Architecture](/architecture/) pages.

### Durable / resumable execution (`CheckpointStore`)

A subagent is the expensive unit of work in an orchestrator-worker run, so it's the unit of
checkpointing. When the orchestrator fans out, each subagent that finishes successfully is
persisted via the `CheckpointStore`, keyed by `(runId, taskId)`. If the swarm dies partway -
a crash, a timeout, a killed process - you **resume by re-invoking the orchestrator with the
same `runId`**: tasks that already have a checkpoint are restored instead of recomputed, and
only the unfinished ones actually run. The resumed run's trace shows restored subagents with a
`restoredFromCheckpoint` attribute so you can see what was skipped versus recomputed.

The policy is deliberate and lives in the orchestrator, not a prompt:

- **Only `ok` results are checkpointed.** A `partial` or `error` result is left uncheckpointed
  on purpose, so it re-runs on resume rather than freezing a bad outcome.
- **Resume is idempotent by key.** Re-running a completed run is a no-op set of restores; there
  is no "did this already happen?" question for the model to get wrong.

The default `CheckpointMemory` writes one JSON file per checkpoint under
`<artifactStoreDir>/checkpoints`. Swap in your own `CheckpointStore` (a database row, a Temporal
activity) and nothing above the seam changes. The record shape is
`specs/schemas/run-checkpoint.schema.json`.

### Deterministic replay (`ReplayChatModel`)

`ReplayChatModel` wraps any provider and keys each request by a stable hash of its
system/messages/tools. In `auto` mode it replays a recorded response or records a new one; in
`replay` mode a cassette miss throws (so CI can guarantee no live call slips in); in `record`
mode it always refreshes. Because it's a `ChatModel` decorator, it composes with
`ResilientChatModel` and everything above the provider layer is unaware. This is what makes the
orchestration logic testable offline and a production failure reproducible - capture one real
run, then replay it for free.

### Human-in-the-loop (`ApprovalProvider`)

Some tool calls are too consequential to run unsupervised. `ToolApprovalGate` marks a set of
tool names as requiring approval; the harness then consults your resolver before executing, and
a denial is returned as a classified `auth` rejection - the tool never runs. The gate lives in
the harness beside scope and budgets, so it's a guarantee no prompt can route around. The
resolver is the seam: block on a human via a UI queue, check a policy, or - composed with the
`CheckpointStore` - suspend the run, persist, and resume once a human answers. The default
`AutoApprove` gates nothing, so existing runs are unchanged.

### Context compaction (`Compactor`)

A long-running agent's message history grows until it threatens the context window.
`SummarizingCompactor` replaces the older middle of the conversation with a summary once the
history exceeds a token threshold, keeping the original task and the most recent turns verbatim -
the same distill-to-a-reference discipline as the artifact store. `run_agent` compacts before
each model call only when you pass a compactor, so it's off (and parity-safe) by default. The
`summarize` step is a seam: the shipped default is a deterministic, model-free digest; wire an
LLM call there for a semantic summary.

### Per-run cost ledger (`summarizeCost`)

`RunBudget` caps token count and the profiler shows a live dollar gauge; the ledger is the
after-the-fact accounting in between. `summarizeCost(spans)` reduces the trace a run already
emitted to a total plus a breakdown by model and by agent role - no extra instrumentation, no
extra model calls. Pair it with `formatCostSummary` for a one-line CLI/log summary.

### Framework interop - plug a framework agent in *underneath* the harness

This is a supported pattern, not a non-goal. If you already built an agent in LangGraph, CrewAI,
or AutoGen, you don't have to rewrite it to adopt these primitives - expose it as an ordinary
`Tool`. Because every tool call routes through the harness, the foreign agent inherits your
scoping, tool-call budget, idempotency, circuit breaker, deterministic error classification, and
a trace span. It runs its own control loop *inside* one governed call; it never runs yours. The
runnable example is [`examples/framework-interop`](https://github.com/routsom/agent-primitives/tree/main/typescript/examples/framework-interop)
(`npm run example:framework-interop` / `uv run python -m examples.framework_interop`). Keep the
[distill-don't-dump](/architecture/) discipline: collapse the framework's verbose transcript to a
summary or an artifact ref before returning it, exactly as a native subagent would.

### The OTLP exporter is a wire-shape, not a transport

`toOtlpSpan(span)` / `to_otlp_span(span)` produces the exact OTLP/JSON span shape a collector
ingests, and `otlpConsoleExporter` prints it. What's deliberately *not* bundled is the network
transport (gRPC/HTTP to a collector, with your endpoint and auth). Adding an OTLP SDK would be
the kind of heavyweight dependency this project avoids - so you wire the last hop, which is a
few lines against your existing observability stack.

## Deliberate non-goals (the framework cliff)

These are genuinely useful in production, but building them *generically* is what turns a
boilerplate into a platform. For each: the seam you'd attach, and why we stopped at the seam.

### Response cache (Redis / semantic)

- **Why not bundled:** it's a QA-path optimization (skip the model for already-answered
  questions), and this system's shape is orchestrator-worker research, not single-turn QA. A
  generic cache would also need your invalidation policy and your "never cache account-specific
  data" rules, which are app-specific and a correctness/security risk to guess at.
- **Seam to attach:** wrap `ChatModel.complete` (it's already a decorator target - see
  `ResilientChatModel`) with a cache-check decorator for read-only paths only.

### Kill switch / feature flags / canary rollout

- **Why not bundled:** these are deployment-infrastructure concerns tied to *how* you ship
  (Kubernetes, a flag service, a load balancer), not to the agent runtime. A control plane
  baked into the library would be an opinion you can't remove.
- **Seam to attach:** the two-level kill switch maps onto existing structure - swarm-level =
  stop routing to the [orchestrator](/architecture/); agent-type-level = reject at the
  [harness](/harness/) scope check for one role. Feature-flag your prompt/model choices at the
  entry point where `resolveResilientModel` and the role definitions are read.

### Cross-session / episodic memory

- **Why not bundled:** durable per-user memory carries its own GDPR/CCPA surface (deletion,
  isolation, PII filtering, poisoning defenses). A boilerplate that ships a memory store makes
  compliance decisions that aren't ours to make.
- **Seam to attach:** it's a new tool (`read_memory` / `write_memory`) plus a store behind the
  same pattern as `ArtifactStore`, keyed by user id. Treat memory writes with the same
  skepticism as tool outputs (memory poisoning is persistent prompt injection).

### APM specifics, A/B testing, automatic rollback

- **Why not bundled:** organizational infrastructure. The trace/audit streams already emit the
  right shape ([Tracing](/tracing/)); point them at Datadog/Splunk/Grafana.
- **Seam to attach:** the OTLP exporter above for traces; the `AuditSink` for the compliance
  stream; your existing metrics pipeline for anomaly detection and rollback triggers.

## The rule of thumb

If an addition is **a typed implementation of an existing interface**, it belongs in your fork
and probably upstream too. If it's **a new engine that decides control flow for you**, it
belongs in *your application on top of* this boilerplate - not inside it. That boundary is the
whole reason this stays usable by both a solo developer and an enterprise without becoming the
next thing you have to escape.
