---
description: Run an example and render its trace output as a readable span tree (turn -> agent -> call)
argument-hint: [typescript|python] [research|single]
allowed-tools: Bash(npm run example:*), Bash(uv run python -m examples.*)
---

Run this boilerplate's example flow, capture its `[trace] {...}` output lines
(specs/schemas/trace-span.schema.json), and render them as a readable tree instead of raw JSON.

Arguments: `$ARGUMENTS` - runtime (`typescript` or `python`, default `typescript`) and example
(`research` or `single`, default `research`). Note the single-agent example emits no trace
spans by design (notes section 1 - it deliberately bypasses the orchestrator); if asked for
`single`, say so instead of running it.

Steps:

1. Run the matching example command (see `/run-task` for the exact commands per
   runtime/example) and capture its full stdout.
2. Extract every line starting with `[trace] ` and parse the JSON that follows.
3. Reconstruct the tree by `parentSpanId` and render it indented by nesting depth, each line
   showing: `kind:name` (e.g. `agent:subagent:sub-1`), `agentRole` and `delegationDepth` if
   present, duration in ms (`endedAt - startedAt`), and `status`. Sort children by
   `startedAt` so parallel subagents appear in the order they actually started.
4. After the tree, call out anything worth a maintainer's attention: any span with
   `status != "ok"`, any `tool_call` span whose `attributes.error` is set, and the total
   count of `agent` spans at `delegationDepth >= 1` (i.e. how many subagents actually ran vs.
   what the lead agent requested).
5. Keep the summary after the tree under 150 words - the tree itself is the main deliverable.
