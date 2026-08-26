---
title: Security
description: Trust boundaries in a multi-agent system, and how this boilerplate enforces them.
---

Multi-agent systems have a wider attack surface than a single agent calling tools: prompt
injection can propagate agent-to-agent, not just tool-to-agent. A compromised or manipulated
instruction picked up by a subagent (from a web page, an MCP tool result, or a remote A2A
response) can ride along in its "findings" straight into the lead agent's next decision
(`reference/multi-agent-architecture-notes.md` section 7). See `SECURITY.md` at the repository
root for how to report a vulnerability.

## The rule everything else follows from

**"Another agent said so" is never an authorization boundary.** Every delegated instruction -
from a subagent, from an [MCP](/mcp/) server, from an [A2A](/a2a/) caller - passes through the
same [harness](/harness/) validation a direct user instruction would. There is no fast path.

## Where this is enforced in code

- **Tool scoping**: `harness/scope.ts` / `harness/scope.py` check every tool call against the
  calling role's `allowedTools` from `specs/agents/*.json` - a subagent can't call
  `spawn_subagents` even if it wanted to, because the harness rejects it before the tool ever
  executes.
- **A2A inbound depth**: `a2a/server.ts` / `a2a/server.py` add the caller's declared delegation
  depth to the local counter rather than trusting a fresh start - a remote agent can't reset the
  depth cap by calling in from outside.
- **Untrusted content**: `specs/prompts/subagent.md` and `specs/prompts/lead-agent.md` both
  instruct agents explicitly not to treat instructions embedded in retrieved tool/web/agent
  output as directives - only the task they were actually given.
- **Least privilege per role**: each role in `specs/agents/` declares its own `allowedTools`,
  `canSpawn`, and `maxDelegationDepth` independently - a role is never implicitly granted
  another role's capabilities.
- **A2A auth + rate limit**: `a2a/server` authenticates (bearer token) and rate-limits per
  caller *before* the request body is read or any model runs (notes section 19) - abusive
  traffic is rejected at near-zero cost.
- **Auth-error redaction**: an `auth`-classified failure is redacted to "not permitted" before
  it reaches the model; the real reason is kept only in the audit log (notes section 12), so a
  probing agent learns nothing about your authorization internals.
- **100% audit trail**: every tool call is recorded with PII-redacted params at the single
  harness chokepoint - an independent forensic record, not reliant on what the model claims
  happened (notes section 11, 22). See [Tracing & audit](/tracing/#the-audit-log).
- **Boundary guardrail seam**: a deterministic `sanitize` hook runs on tool output before it
  reaches the model - never an LLM call on the safety path (notes section 8). Ships as identity;
  wire your rules (see [Extending it](/extending/)).

## Reporting a vulnerability

Use GitHub's private vulnerability reporting (Security tab → Report a vulnerability) rather than
a public issue. Full details in `SECURITY.md`.

## What to look for when reviewing a change here

If a PR adds a new way for one agent (or an external MCP/A2A caller) to trigger another agent's
action, and that path doesn't go through `harness.execute` / `Harness.execute`, that's a
security regression regardless of how convenient the shortcut is.
