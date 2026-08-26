from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class HarnessCaps:
    max_subagents: int
    max_delegation_depth: int
    max_tool_calls_per_subagent: int
    # Session-level token ceiling shared across the whole run (lead + all subagents). 0 = unlimited.
    max_run_tokens: int


@dataclass
class ResilienceConfig:
    timeout_ms: int
    max_retries: int
    base_delay_ms: int


@dataclass
class Config:
    default_provider: str
    caps: HarnessCaps
    resilience: ResilienceConfig
    artifact_store_dir: str


def _int_from_env(name: str, fallback: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def load_config() -> Config:
    return Config(
        default_provider=os.environ.get("DEFAULT_PROVIDER", "mock"),
        caps=HarnessCaps(
            max_subagents=_int_from_env("MAX_SUBAGENTS", 8),
            max_delegation_depth=_int_from_env("MAX_DELEGATION_DEPTH", 2),
            max_tool_calls_per_subagent=_int_from_env("MAX_TOOL_CALLS_PER_SUBAGENT", 15),
            max_run_tokens=_int_from_env("MAX_RUN_TOKENS", 250000),
        ),
        resilience=ResilienceConfig(
            timeout_ms=_int_from_env("MODEL_TIMEOUT_MS", 60000),
            max_retries=_int_from_env("MAX_MODEL_RETRIES", 2),
            base_delay_ms=_int_from_env("RETRY_BASE_DELAY_MS", 500),
        ),
        artifact_store_dir=os.environ.get("ARTIFACT_STORE_DIR", ".artifacts"),
    )
