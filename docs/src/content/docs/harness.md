---
title: Harness
description: The shared infrastructure every agent's tool call routes through - validation, scoping, idempotency, and the two circuit breakers.
---

The harness is the one piece of shared infrastructure every agent - lead, subagent, citation,
judge - routes every tool call through. There is no agent-to-agent shortcut around it; "another
agent said so" is never itself an authorization boundary (see
`reference/multi-agent-architecture-notes.md` section 7).

## What it does

1. **Scope check** - a role may only call tools explicitly listed in its
   `specs/agents/<role>.json` `allowedTools`. A search-only subagent never holds
   `spawn_subagents` even if the lead agent does.
2. **Idempotency** - concurrent or repeated tool calls with the same idempotency key resolve to
   a single in-flight execution, not duplicate side effects.
3. **Budget enforcement** - two independent circuit breakers:
   - **Delegation-depth cap** - bounds how many agent-to-agent hops a task can accumulate,
     rejecting further spawning once exceeded.
   - **Tool-call budget** - bounds how many tool calls a single agent's own loop can make
     before it's forced to stop and report partial results.
4. **Execution** - looks up the tool by name and runs it with a `ToolContext` carrying the
   calling role, delegation depth, and a narrow `ToolRuntime` interface back into the
   orchestrator (for `spawn_subagents`, `write_artifact`, `read_artifact`, `save_plan`).

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
