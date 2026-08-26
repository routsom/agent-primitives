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
| **Artifact storage** | `ArtifactStore` (`artifacts/`) | local filesystem | S3, GCS, a database - implement `write`/`read` |
| **Plan storage** | `PlanStore` (`memory/`) | local filesystem | A durable job store (Postgres, DynamoDB) |
| **Audit log** | `AuditSink` (`harness/`) | `NoopAuditSink` (silent) | `ConsoleAuditSink`, `JsonlAuditSink`, or your log pipeline |
| **Trace export** | `Tracer` `onSpanEnd` sink + `toOtlpSpan` | console JSON | `otlpConsoleExporter`, then wire the OTLP wire-shape to your collector |
| **Rate limiting** | `SlidingWindowRateLimiter` | in-memory, single process | Back the same interface with Redis for multi-instance |
| **Boundary guardrail** | `Sanitize` hook (`harness/`) | identity (no-op) | Strip injected instructions, scrub PII, enforce allowed shapes |
| **Tool circuit breaker** | `ToolCircuitBreaker` | in-memory per-process | Shared state across instances via Redis if you run many replicas |

Each is passed via the `Harness` / `Orchestrator` options - see the [Harness](/harness/) and
[Architecture](/architecture/) pages.

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
