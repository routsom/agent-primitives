"""Deterministic USD cost from token usage, using the shared price table in specs/pricing.json.
This turns the token counts every span already carries into the dollar figures the profiler
dashboard shows and that a real cost budget would cap. Prices are estimates you edit to match
your contract - not billing truth. Mirrors typescript/src/cost/pricing.ts."""

from __future__ import annotations

import json
import os
from functools import cache

from ..harness.schemas import REPO_ROOT
from ..providers.types import TokenUsage


@cache
def _table() -> dict[str, dict]:
    raw = json.loads((REPO_ROOT / "specs" / "pricing.json").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def price_key(provider: str, model: str) -> str:
    return f"{provider}:{model}"


def compute_cost_usd(provider: str, model: str, usage: TokenUsage) -> float:
    """Cost in USD for one model call. `provider:model` keys the table; an unknown key costs 0.
    If the provider is the mock and MOCK_PRICE_AS is set, mock tokens are priced at that real
    model's rate so offline demos show realistic numbers."""
    key = price_key(provider, model)
    if provider == "mock" and os.environ.get("MOCK_PRICE_AS"):
        key = os.environ["MOCK_PRICE_AS"]

    price = _table().get(key)
    if not price:
        return 0.0

    cached = usage.cached_input_tokens or 0
    fresh_input = max(0, usage.input_tokens - cached)
    cached_rate = price.get("cachedInputPerMTok", price["inputPerMTok"])
    return (
        fresh_input * price["inputPerMTok"]
        + cached * cached_rate
        + usage.output_tokens * price["outputPerMTok"]
    ) / 1_000_000
