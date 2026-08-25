---
title: Tracing
description: Nested spans from turn to agent to individual model/tool calls, OpenTelemetry-compatible by construction.
---

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
`onSpanEnd` / `on_span_end` callback for a real OpenTelemetry exporter in production; the span
shape doesn't need to change.

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
