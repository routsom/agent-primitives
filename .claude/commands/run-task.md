---
description: Run the research-task (or single-agent baseline) example end to end and summarize the result
argument-hint: [typescript|python] [research|single]
allowed-tools: Bash(npm run example:*), Bash(uv run python -m examples.*)
---

Run this boilerplate's example flow and report back concisely.

Arguments: `$ARGUMENTS` - first word is the runtime (`typescript` or `python`, default
`typescript`), second word is which example (`research` for the full orchestrator-worker flow,
`single` for the single-agent baseline, default `research`).

Steps:

1. Parse `$ARGUMENTS` for runtime and example choice, defaulting as above.
2. Run the matching command:
   - TypeScript + research: `npm run example:research` in `typescript/`
   - TypeScript + single: `npm run example:single-agent` in `typescript/`
   - Python + research: `uv run python -m examples.research_task` in `python/`
   - Python + single: `uv run python -m examples.single_agent` in `python/`
3. Summarize in under 200 words: which provider ran (mock unless an API key is set), whether
   subagents were spawned and how many, whether any artifacts were written, whether the run
   completed `ok` or `partial`, and the total span count from the trace output. Don't paste the
   raw trace JSON - synthesize it.
4. If the command fails, show the actual error rather than guessing at the cause.
