from __future__ import annotations

import os

from .mock import MockChatModel
from .replay import ReplayChatModel, ReplayMode
from .resilient import ResilienceOptions, ResilientChatModel
from .types import ChatModel

__all__ = [
    "ChatModel",
    "MockChatModel",
    "ReplayChatModel",
    "ReplayMode",
    "ResilientChatModel",
    "ResilienceOptions",
    "resolve_provider",
    "resolve_resilient_model",
]


def resolve_provider(name: str) -> ChatModel:
    """Resolves a logical provider name (as used in specs/agents/*.json modelPreference) to a
    concrete ChatModel, falling back to the mock provider when no key is configured. This is
    the entire "multi-LLM support" surface - no routing library, just a lookup."""
    if name == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return MockChatModel()
        from .anthropic_provider import AnthropicChatModel

        return AnthropicChatModel(key)
    if name == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return MockChatModel()
        from .openai_provider import OpenAIChatModel

        return OpenAIChatModel(key)
    if name == "google":
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            return MockChatModel()
        from .gemini_provider import GeminiChatModel

        return GeminiChatModel(key)
    return MockChatModel()


def resolve_resilient_model(
    name: str,
    resilience: ResilienceOptions,
    fallback_providers: list[str] | None = None,
) -> ChatModel:
    """Resolves the provider AND wraps it in the resilience decorator (timeout + retry +
    fallback). Entry points should use this rather than resolve_provider directly, so every
    real model call gets timeout/retry protection. Fallbacks are opt-in via
    fallback_providers - by default there are none, to avoid surprising cross-provider calls;
    add them deliberately when you want model/region failover (notes section 15)."""
    primary = resolve_provider(name)
    resilience.fallbacks = [resolve_provider(p) for p in (fallback_providers or [])]
    return ResilientChatModel(primary, resilience)
