"""The baseline this boilerplate deliberately keeps around: one well-prompted agent, no
orchestrator, no subagents. Multi-agent (examples/research_task.py) is an escalation you earn
with evidence a single agent can't clear - not the default. Compare the two before reaching
for the orchestrator-worker path on a real task.

Run with: uv run python -m examples.single_agent
"""

from __future__ import annotations

import asyncio

from multiagent_boilerplate.config import load_config
from multiagent_boilerplate.providers import resolve_provider
from multiagent_boilerplate.providers.types import ChatCompletionRequest, ProviderMessage, TextBlock, text_of

QUERY = "What are the main tradeoffs between orchestrator-worker and sequential-pipeline multi-agent topologies?"


async def main() -> None:
    config = load_config()
    model = resolve_provider(config.default_provider)

    print(f'[single-agent] using provider "{model.provider}" ({model.model})')

    result = await model.complete(
        ChatCompletionRequest(
            system="You are a helpful, direct assistant. Answer in a few sentences.",
            messages=[ProviderMessage(role="user", content=[TextBlock(text=QUERY)])],
        )
    )

    print("\n[single-agent result]")
    print(text_of(result.message))


if __name__ == "__main__":
    asyncio.run(main())
