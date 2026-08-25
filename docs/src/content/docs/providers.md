---
title: Providers (multi-LLM)
description: How this boilerplate supports Anthropic, OpenAI, and Gemini without a routing library.
---

Multi-LLM support is a thin `ChatModel` interface with one hand-rolled adapter per vendor's
*official* SDK - no third-party routing library (LiteLLM, etc.) sitting between your code and
the provider.

```ts
// typescript/src/providers/types.ts
interface ChatModel {
  readonly provider: string;
  readonly model: string;
  complete(request: ChatCompletionRequest): Promise<ChatCompletionResult>;
}
```

```py
# python/src/multiagent_boilerplate/providers/types.py
class ChatModel(Protocol):
    provider: str
    model: str
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult: ...
```

Each adapter normalizes messages, tool calls, and token usage into the shared shape defined by
`specs/schemas/provider-message.schema.json`, so everything above the provider layer (harness,
agents, orchestrator) never touches a vendor-specific type.

## Built-in adapters

| Logical name | Backing SDK | Env var | Notes |
|---|---|---|---|
| `anthropic` | `@anthropic-ai/sdk` / `anthropic` | `ANTHROPIC_API_KEY` | Prompt caching enabled on the system prompt in the TypeScript adapter |
| `openai` | `openai` | `OPENAI_API_KEY` | Chat Completions API |
| `google` | `@google/genai` / `google-genai` | `GOOGLE_API_KEY` | |
| `mock` | none | - | Deterministic, offline, zero network calls - the default |

## Resolution

`resolveProvider(name)` / `resolve_provider(name)` looks up the logical name from
`DEFAULT_PROVIDER` (or a role's `modelPreference` in `specs/agents/*.json`), and falls back to
the mock provider if the corresponding API key isn't set - this is the entire routing logic.
There's no dynamic model-selection heuristic to reason about beyond that.

```
DEFAULT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

## The mock provider

`providers/mock.ts` and `providers/mock.py` implement a small deterministic state machine keyed
on which role's prompt is active and how many turns have happened in that agent's own context.
It's not a toy - it's what CI runs against, and what `npm run example:research` /
`uv run python -m examples.research_task` use by default so the whole system is inspectable with
zero setup. Both language implementations produce structurally equivalent tool-call sequences
from the same input, which is what `scripts/check_parity.py` checks (see
[Architecture](/architecture/#cross-language-parity)).

## Adding a new provider

1. Write a thin adapter implementing `ChatModel` over the vendor's official SDK, in
   `providers/<vendor>.ts` / `providers/<vendor>_provider.py`. Match the existing adapters'
   shape - don't reach for a routing library (see [Architecture](/architecture/#why-no-orchestration-framework)).
2. Register it in `resolveProvider` / `resolve_provider`.
3. Do this in **both** runtimes if you want it usable from either - `specs/agents/*.json`'s
   `modelPreference` field is provider-name-only (no concrete model IDs, since those change
   frequently), so the two runtimes don't need identical model strings, just a consistent
   logical provider name.
