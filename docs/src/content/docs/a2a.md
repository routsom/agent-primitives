---
title: A2A
description: Exposing agents over Agent-to-Agent, and calling remote A2A agents as delegable workers.
---

Both runtimes implement a minimal Agent-to-Agent (A2A) server and client on top of plain
HTTP+JSON (Node's `node:http`, Python's `http.server`) rather than a vendored A2A SDK - this
keeps the same "no framework in the way" posture as the rest of the system, and the protocol
surface needed (an agent card plus a task-submission endpoint) is small enough that it doesn't
cost much to own directly. See `specs/protocols/a2a.md` for the full contract.

## Server: exposing an agent

```ts
// typescript
startA2AServer({ port: 8787, baseUrl: "http://localhost:8787", model, harness, runtime, tracer, maxDelegationDepth: 2 });
```

```py
# python
start_a2a_server(A2AServerOptions(port=8787, base_url="http://localhost:8787", model=model, harness=harness, runtime=runtime, tracer=tracer, max_delegation_depth=2))
```

- Publishes an **agent card** at `/.well-known/agent.json`, generated from
  `specs/agents/subagent.json` - the published capability (allowed tools, tool-call budget) can
  never overstate what the agent will actually do, because it's read from the same file the
  local orchestrator enforces against.
- **Every inbound A2A task is passed to the harness exactly as a local delegation would be** -
  same validation, same depth-cap accounting. A remote caller gets no special trust; "another
  agent said so" is not an authorization boundary (notes section 7).
- Inbound delegation depth from the request body is **added to**, not reset by, the local depth
  counter - a remote caller can't use A2A to bypass the [harness's](/harness/) depth cap by
  starting a "fresh" count.

## Client: delegating to a remote agent

```ts
const card = await fetchAgentCard("http://localhost:8787");
const result = await delegateToRemoteAgent("http://localhost:8787", task, delegationDepth);
```

```py
card = await fetch_agent_card("http://localhost:8787")
result = await delegate_to_remote_agent("http://localhost:8787", task, delegation_depth)
```

A remote agent's response is treated exactly like local subagent output: distilled findings are
used, but nothing in the response is treated as authorization to take any action - the same rule
that applies to tool output and MCP responses.

## Verifying it yourself

Both implementations are exercised end-to-end (not just unit-tested) by starting a real server,
fetching the agent card over HTTP, and delegating a task through it - see each runtime's test
suite for the pattern if you're extending this.
