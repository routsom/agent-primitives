---
title: Claude Code integration
description: The hooks, subagents, and slash commands this repository ships for agentic coding.
---

This repository is built to be worked on *with* Claude Code (or any coding agent that respects
`CLAUDE.md`), not just to produce one. See `CLAUDE.md` at the repository root for the
authoritative navigation guide - this page covers the `.claude/` tooling itself.

## Hooks (`.claude/settings.json`)

- **PostToolUse** (`Edit`/`Write`) → `.claude/hooks/post_edit_lint.py` lints the exact file just
  touched - ESLint for `.ts`/`.tsx` under `typescript/`, `ruff` for `.py` under `python/`.
  Fast, scoped feedback instead of waiting for a full CI run.
- **Stop** → `.claude/hooks/stop_verify.py` checks `git status` for uncommitted changes under
  `typescript/` and/or `python/` and runs that runtime's typecheck+test (or lint+test) before
  the turn ends, blocking with a clear failure summary if something's broken. A runtime with no
  changes is skipped entirely, so this stays fast on small edits.

Both hooks are plain Python scripts with no dependencies beyond the standard library - read
them directly if you want to see exactly what runs.

## Subagents (`.claude/agents/`)

Four subagents let you interactively iterate on this boilerplate's own prompts
(`specs/prompts/*.md`) without running the full stack:

| Subagent | Wraps | Use it to |
|---|---|---|
| `lead-agent` | `specs/prompts/lead-agent.md` | Test delegation/scaling decisions for a candidate query |
| `subagent-worker` | `specs/prompts/subagent.md` | Test distillation and dead-end-recognition behavior for a given `AgentTask` |
| `citation-agent` | `specs/prompts/citation-agent.md` | Test attribution strictness against a set of findings |
| `eval-judge` | `specs/prompts/judge.md` | Test rubric scoring against a task/response/trace |

Each one **reads the shared prompt file live** rather than duplicating its content in the
subagent definition - so there's nothing to keep in sync when you edit `specs/prompts/`.

## Slash commands (`.claude/commands/`)

- **`/run-task [typescript|python] [research|single]`** - runs the matching example end to end
  and summarizes the result (provider used, subagent count, artifacts written, final status)
  without pasting raw trace JSON.
- **`/eval [typescript|python]`** - runs the eval seed set and reports scores, flagging whether
  any `flag_for_human_review` looks legitimate.
- **`/trace [typescript|python] [research|single]`** - runs an example, captures its `[trace]`
  output, and renders it as an indented span tree instead of raw JSON lines.

## The one invariant to know before editing agent behavior

`specs/` is the source of truth. If you change a prompt, schema, or agent role definition,
update **both** `typescript/` and `python/` in the same change - run
`python3 scripts/check_parity.py` from the repo root afterward; it will catch a one-sided edit.
