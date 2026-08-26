---
title: Harness
description: The guarantees layer every agent's tool call routes through - scoping, idempotency, classification, budgets, circuit breaking, audit, and the boundary guardrail.
---

The harness is the one piece of shared infrastructure every agent - lead, subagent, citation,
judge - routes every tool call through. There is no agent-to-agent shortcut around it; "another
agent said so" is never itself an authorization boundary (see
`reference/multi-agent-architecture-notes.md` section 7). It is where the boilerplate's central
principle lives: **the model owns judgment, the harness owns guarantees.**

`Harness.execute` returns a typed `ToolOutcome` (`ok` / `error` / `rejected`) as data - errors
are classified and returned, never thrown into the agent loop. See
[Reliability & guarantees](/reliability/) for the full catalogue; this page covers how a call
flows through it.

## The stages of `execute`

1. **Scope check** - a role may only call tools in its `specs/agents/<role>.json` `allowedTools`.
   A search-only subagent never holds `spawn_subagents` even if the lead agent does. A violation
   classifies as `auth` (no retry, security-logged).
2. **Circuit breaker** - if this tool's backend is failing system-wide, short-circuit
   immediately as transient rather than pile on another timeout.
3. **Idempotency** - concurrent or repeated calls with the same key resolve to a single
   in-flight execution, not duplicate side effects.
4. **Execution** - runs the tool with a `ToolContext` (calling role, delegation depth, and a
   narrow `ToolRuntime` back into the orchestrator).
5. **Classify or sanitize** - on failure, classify the error (`transient/permanent/validation/
   auth`) and record it against the breaker; on success, pass output through the boundary
   guardrail before returning it to the model.
6. **Audit** - emit a 100%-coverage, PII-redacted audit record for *every* outcome.

Budgets (per-agent tool-call cap, delegation-depth cap, and the run-wide session token ceiling)
are enforced around this loop - see [Reliability & guarantees](/reliability/#budgets---three-independent-circuit-breakers).

## Configuring it

```ts
new Harness(tools, {
  auditSink: new ConsoleAuditSink(),          // default: silent NoopAuditSink
  circuitBreaker: { failureThreshold: 5, windowMs: 60000, cooldownMs: 30000 },
  sanitize: (boundary, content) => content,    // default: identity
});
```

```py
Harness(tools, HarnessOptions(
    audit_sink=ConsoleAuditSink(),
    circuit_breaker=CircuitBreakerOptions(failure_threshold=5, window_ms=60000, cooldown_ms=30000),
    sanitize=my_sanitizer,
))
```

## Validation without a schema library

`specs/schemas/*.json` are the source of truth for shapes like `AgentTask`, `ArtifactRef`, and
`TraceSpan`. Rather than pulling in a full JSON Schema engine (Ajv in TS, a Pydantic-model
duplicate in Python), both runtimes ship a small (~60-line) hand-rolled structural validator
that reads the schema files directly and checks `required`/`type`/`enum`. This means there's
exactly one place that can drift from `specs/` - the validator logic itself, which is
deliberately trivial - rather than a second, parallel type system to keep in sync.

## Least privilege at the role level

```json
// specs/agents/subagent.json
{
  "role": "subagent",
  "allowedTools": ["search_web", "read_file", "write_artifact", "mcp_call"],
  "canSpawn": [],
  "maxDelegationDepth": 0,
  "budget": { "maxToolCalls": 15 }
}
```

A subagent can't spawn further subagents (`canSpawn: []`, `maxDelegationDepth: 0`) and can't
touch `spawn_subagents` or `save_plan` at all - those aren't in its `allowedTools`. This is
enforced by the harness, not by convention or prompt wording.

## Extending it

Any new spawn path (a new way for one agent to trigger another, including over
[A2A](/a2a/)) must route through the harness so the existing caps apply. This is the rule
called out in `CLAUDE.md` - it's the single most important invariant in this codebase.
