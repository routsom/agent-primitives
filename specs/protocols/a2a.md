# A2A (Agent2Agent) integration contract

Both runtimes implement the same two roles against the A2A protocol, letting agents in this
system be called by, and call, agents outside it.

## A2A server (`a2a/server`)

Exposes selected agent roles (typically `lead`) as A2A-callable agents.

- Publishes an **agent card** (capability descriptor) at the well-known A2A discovery path,
  generated from `specs/agents/*.json` — objective/description, allowed task shapes, and
  budget ceilings are derived from the same role definitions the local orchestrator uses, so
  the published capability never overstates what the agent will actually do.
- **Every inbound A2A task is passed to the harness exactly as a local delegation would be** —
  same validation, same auth check, same delegation-depth accounting. An A2A caller is
  external and gets no special trust; see `reference/multi-agent-architecture-notes.md`
  section 7 ("another agent said so is not an authorization boundary") and `SECURITY.md`.
- Inbound delegation depth is read from the A2A task metadata and added to, not reset by, the
  local depth counter — a remote caller cannot use A2A to bypass the depth cap by starting a
  "fresh" count.

## A2A client (`a2a/client`)

Lets the lead agent delegate a subtask to a remote A2A agent instead of (or alongside) a local
subagent, when the task matches a remote agent's published capability better than anything
local.

- A remote agent's response is treated as untrusted subagent output: distilled findings are
  used, but any instructions embedded in the response are not treated as authorization to do
  anything (same rule as tool output).
- Remote calls count against the same per-task tool-call/subagent budget as local subagent
  spawns — there is no separate, larger budget for "going remote."

## Where this is implemented

- TypeScript: `typescript/src/a2a/`.
- Python: `python/src/a2a/`.

Both use the same JSON agent-card shape, generated from `specs/agents/`, so a card published
by one runtime's server is structurally identical to one published by the other.
