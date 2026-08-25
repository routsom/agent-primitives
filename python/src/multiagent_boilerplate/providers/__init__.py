from __future__ import annotations

import os

from .mock import MockChatModel
from .types import ChatModel

__all__ = ["ChatModel", "MockChatModel", "resolve_provider"]


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
