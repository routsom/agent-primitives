"""Deterministic replay ("VCR") for the model dependency. Wraps a ChatModel and, keyed by a hash
of each request, records the response to a cassette file - then replays it on the next run without
touching the network. This is what makes the "every layer is inspectable" claim *testable*:
capture one real run, then regression-test the orchestration logic offline, for free, and
reproduce a production failure exactly. Because it's a ChatModel itself, nothing above the
provider layer knows replay is happening - it's a decorator, like ResilientChatModel.

Modes:
  - "auto"   (default): replay a request that's in the cassette; otherwise call the base model
             and record it. A missing cassette records itself on first run.
  - "replay": replay only; a request not in the cassette raises. Use in CI to guarantee no
             network call sneaks in and the recording is complete.
  - "record": always call the base model and (re)record. Use to refresh a cassette."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from ..harness.errors import ClassifiedError
from .types import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ChatModel,
    ProviderMessage,
    TextBlock,
    TokenUsage,
    ToolCallBlock,
    ToolResultBlock,
)

ReplayMode = Literal["auto", "replay", "record"]


def request_hash(provider: str, model: str, request: ChatCompletionRequest) -> str:
    """Stable hash of the semantically-relevant request fields."""
    canonical = json.dumps(
        {
            "provider": provider,
            "model": model,
            "system": request.system or "",
            "messages": [asdict(m) for m in request.messages],
            "tools": [asdict(t) for t in request.tools],
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class ReplayChatModel:
    def __init__(self, base: ChatModel, cassette_path: str | Path, mode: ReplayMode = "auto") -> None:
        self._base = base
        self._path = Path(cassette_path)
        self._mode: ReplayMode = mode
        self._cassette: dict[str, dict] = self._load()

    @property
    def provider(self) -> str:
        return self._base.provider

    @property
    def model(self) -> str:
        return self._base.model

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        key = request_hash(self._base.provider, self._base.model, request)
        recorded = self._cassette.get(key)

        if self._mode != "record" and recorded is not None:
            return _result_from_dict(recorded["response"])
        if self._mode == "replay":
            raise ClassifiedError(
                "permanent",
                f'replay: no cassette entry for request {key} in {self._path} (run in "record" or "auto" mode first)',
            )

        response = await self._base.complete(request)
        self._cassette[key] = {
            "provider": self._base.provider,
            "model": self._base.model,
            "request": {"system": request.system, "messages": [asdict(m) for m in request.messages]},
            "response": _result_to_dict(response),
        }
        self._save()
        return response

    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._cassette, indent=2), encoding="utf-8")


def _result_to_dict(result: ChatCompletionResult) -> dict:
    return {"message": asdict(result.message), "usage": asdict(result.usage), "stop_reason": result.stop_reason}


def _block_from_dict(data: dict) -> TextBlock | ToolCallBlock | ToolResultBlock:
    kind = data.get("type")
    if kind == "text":
        return TextBlock(text=data["text"])
    if kind == "tool_call":
        return ToolCallBlock(id=data["id"], name=data["name"], input=data["input"])
    if kind == "tool_result":
        return ToolResultBlock(
            tool_call_id=data["tool_call_id"], output=data["output"], is_error=data.get("is_error", False)
        )
    raise ValueError(f"replay: unknown content block type {kind!r}")


def _result_from_dict(data: dict) -> ChatCompletionResult:
    message = ProviderMessage(
        role=data["message"]["role"],
        content=[_block_from_dict(b) for b in data["message"]["content"]],
        name=data["message"].get("name"),
    )
    usage = TokenUsage(
        input_tokens=data["usage"]["input_tokens"],
        output_tokens=data["usage"]["output_tokens"],
        cached_input_tokens=data["usage"].get("cached_input_tokens"),
    )
    return ChatCompletionResult(message=message, usage=usage, stop_reason=data["stop_reason"])
