---
title: "Quickstart: TypeScript"
description: Clone, install, and run the TypeScript runtime end to end in under a minute.
---

## Requirements

- Node.js 20+
- npm (ships with Node)

## Install

```bash
git clone https://github.com/routsom/agent-primitives.git
cd agent-primitives/typescript
npm install
```

## Run the full orchestrator-worker flow

No API key required - this uses the deterministic mock provider by default.

```bash
npm run example:research
```

You'll see a lead agent decompose the query, spawn two parallel subagents (each in its own
isolated context), each subagent search and write an artifact, and a citation agent synthesize
the final answer - with a full nested trace (`turn → agent → model/tool call`) printed as it
runs.

## Run the single-agent baseline

Multi-agent is an escalation, not a default (see [Architecture](/architecture/)). This example
shows the one-agent-no-orchestrator baseline it should be compared against:

```bash
npm run example:single-agent
```

## Use a real model

Copy `.env.example` to `.env` and set a provider key:

```bash
cp .env.example .env
# then edit .env:
# ANTHROPIC_API_KEY=sk-ant-...
# DEFAULT_PROVIDER=anthropic
```

Supported logical providers: `anthropic`, `openai`, `google`, `mock` (default). See
[Providers](/providers/) for how the adapter layer resolves this.

## Everything else

```bash
npm run typecheck   # strict TypeScript, no emit
npm run lint         # eslint
npm test              # vitest
npm run build        # tsup -> dist/
npm run eval          # LLM-judge eval seed set, see /evals/
```

## Where to go next

- [Architecture](/architecture/) for the module map and the reasoning behind each layer.
- [Harness](/harness/) for how tool calls are validated, scoped, and budget-capped.
- [Claude Code integration](/claude-code/) if you're extending this repo with Claude Code.
