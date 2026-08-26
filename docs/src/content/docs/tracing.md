---
title: Tracing & audit
description: Two separate streams - a sampled eval trace and a 100%-coverage audit log - that share correlation IDs but have different retention and guarantees.
---

There are **two** logging streams here, deliberately separate (notes section 12, 22): a **trace**
for quality measurement (sampled, async) and an **audit log** for compliance and forensics (100%
coverage, PII-redacted). They share correlation IDs but have different retention, access control,
and completeness guarantees. Conflating them is a mistake - the audit log must be complete even
when trace sampling drops a span.


Multi-agent systems are non-deterministic between runs even with identical prompts, which makes
"the agent didn't find something obvious" reports very hard to root-cause without full tracing -
was it a bad search query, a poor tool choice, a tool failure, or bad delegation from the lead?
(`reference/multi-agent-architecture-notes.md` section 11.)

## Span shape

Every span follows `specs/schemas/trace-span.schema.json` - one schema, both runtimes, and
structurally compatible with an OpenTelemetry span so it can be exported as-is:

```json
{
  "spanId": "...",
  "traceId": "...",
  "parentSpanId": "...",
  "kind": "turn" | "agent" | "model_call" | "tool_call" | "a2a_call",
  "name": "subagent:sub-1",
  "agentRole": "subagent",
  "delegationDepth": 1,
  "startedAt": "...",
  "endedAt": "...",
  "status": "ok" | "error" | "partial",
  "tokenUsage": { "inputTokens": 46, "outputTokens": 30 }
}
```

## Nesting

`turn → agent → model_call | tool_call | a2a_call`. Every subagent spawned by
`spawn_subagents` gets its own `agent` span nested under the run's `turn` span, with its own
`model_call` and `tool_call` children - so a trace for a two-subagent research task naturally
shows both subagents' full call sequences side by side, in the order they actually started.

## Default exporter

Both runtimes default to printing each completed span as a `[trace] {...}` JSON line to stdout -
zero setup, and exactly what CI and the example scripts show you. Swap the `Tracer`'s
`onSpanEnd` / `on_span_end` callback for a real exporter in production; the span shape doesn't
need to change.

### OTLP export seam

`toOtlpSpan(span)` / `to_otlp_span(span)` maps a span to the OpenTelemetry OTLP/JSON shape, and
`otlpConsoleExporter` / `otlp_console_exporter` is a ready sink you can pass as `onSpanEnd`. What
isn't bundled is the network transport to a collector (endpoint + auth) - that last hop is a few
lines against your own stack, and pulling in an OTLP SDK would be exactly the heavyweight
dependency this boilerplate avoids. See [Extending it](/extending/#the-otlp-exporter-is-a-wire-shape-not-a-transport).

## The audit log

The audit stream is separate from the trace and emitted at the single harness chokepoint, so
coverage is **structural, not best-effort** - every tool call produces one entry regardless of
outcome:

```json
{
  "timestamp": "2026-...Z",
  "traceId": "...", "sessionId": "...", "requestId": "...",
  "agentRole": "subagent", "toolName": "search_web",
  "idempotencyKey": "call-search-0", "delegationDepth": 1,
  "paramsRedacted": { "query": "x", "apiKey": "[redacted]" },
  "resultStatus": "ok"
}
```

Params are **redacted at the point of logging** - sensitive keys (token, password, api_key,
email, amount, ...) are replaced before the entry is written, never stored raw. Wire an
`AuditSink` (`ConsoleAuditSink`, `JsonlAuditSink`, or your own) into the `Harness`; the shipped
server entrypoint turns it on. The default in examples is silent so trace output stays readable.

## Reading a trace without squinting at JSON

The [`/trace` Claude Code command](/claude-code/) runs an example and renders its trace output
as an indented span tree instead of raw JSON lines - useful when you're debugging a prompt or
harness change locally.

## What to actually track

Per the notes, track **structure**, not just content: which agent spawned which, delegation
depth, and handoff shape, as a monitoring layer distinct from reading individual conversation
content. This gives you system-level visibility (and can be designed to preserve privacy, by
monitoring structure rather than content) while still surfacing where coordination is breaking
down.
