import { AnthropicChatModel } from "./anthropic.js";
import { GeminiChatModel } from "./gemini.js";
import { MockChatModel } from "./mock.js";
import { OpenAIChatModel } from "./openai.js";
import { ResilientChatModel, type ResilienceOptions } from "./resilient.js";
import { ReplayChatModel, type ReplayOptions, type ReplayMode } from "./replay.js";
import type { ChatModel } from "./types.js";

export * from "./types.js";
export { AnthropicChatModel, OpenAIChatModel, GeminiChatModel, MockChatModel, ResilientChatModel, ReplayChatModel };
export type { ResilienceOptions, ReplayOptions, ReplayMode };

export type ProviderName = "anthropic" | "openai" | "google" | "mock";

/**
 * Resolves a logical provider name (as used in specs/agents/*.json modelPreference) to a
 * concrete ChatModel, falling back to the mock provider when no key is configured. This is
 * the entire "multi-LLM support" surface - no routing library, just a lookup.
 */
export function resolveProvider(name: ProviderName): ChatModel {
  switch (name) {
    case "anthropic": {
      const key = process.env["ANTHROPIC_API_KEY"];
      if (!key) return new MockChatModel();
      return new AnthropicChatModel(key);
    }
    case "openai": {
      const key = process.env["OPENAI_API_KEY"];
      if (!key) return new MockChatModel();
      return new OpenAIChatModel(key);
    }
    case "google": {
      const key = process.env["GOOGLE_API_KEY"];
      if (!key) return new MockChatModel();
      return new GeminiChatModel(key);
    }
    case "mock":
    default:
      return new MockChatModel();
  }
}

/**
 * Resolves the provider AND wraps it in the resilience decorator (timeout + retry + fallback).
 * Entry points should use this rather than resolveProvider directly, so every real model call
 * gets timeout/retry protection. Fallbacks are opt-in via `fallbackProviders` - by default there
 * are none, to avoid surprising cross-provider calls; add them deliberately when you want
 * model/region failover (notes section 15).
 */
export function resolveResilientModel(
  name: ProviderName,
  resilience: ResilienceOptions,
  fallbackProviders: ProviderName[] = [],
): ChatModel {
  const primary = resolveProvider(name);
  const fallbacks = fallbackProviders.map(resolveProvider);
  return new ResilientChatModel(primary, { ...resilience, fallbacks });
}
