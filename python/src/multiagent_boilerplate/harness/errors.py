"""Deterministic error classification (notes section 12). The harness - not the model, not a
regex on a message string - decides an error's type, and retryability is derived from the type.
This is what lets the orchestrator apply the right policy (bounded retry vs. surface-as-final
vs. security-log) without ever asking the model 'should I retry?'.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ToolErrorType = Literal["transient", "permanent", "validation", "auth"]


@dataclass
class ToolError:
    type: ToolErrorType
    message: str
    retryable: bool
    code: str | None = None


@dataclass
class ToolOutcome:
    """The harness's Result<T, E> - the typed outcome of a tool call. `ok` carries output;
    `error` means the tool ran and failed; `rejected` means the harness refused before
    execution (scope, validation, circuit breaker). Errors are returned as data, never raised
    across the harness boundary into the agent loop."""

    status: Literal["ok", "error", "rejected"]
    output: object = None
    error: ToolError | None = None


class ClassifiedError(Exception):
    """Raised by a tool (or the harness) to assert a specific classification rather than
    relying on heuristics."""

    def __init__(self, error_type: ToolErrorType, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.type = error_type
        self.code = code


class ValidationFailure(ClassifiedError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__("validation", message, code)


class AuthFailure(ClassifiedError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__("auth", message, code)


_TRANSIENT_CODE = re.compile(
    r"\b(429|500|502|503|504|522|524|529|ETIMEDOUT|ECONNRESET|ECONNREFUSED|EAI_AGAIN|ENOTFOUND)\b", re.I
)
_TRANSIENT_TEXT = re.compile(
    r"\b(timeout|timed out|temporarily|rate limit|overloaded|too many requests"
    r"|try again|unavailable|connection reset)\b",
    re.I,
)
_AUTH_TEXT = re.compile(r"\b(unauthorized|forbidden|permission|not permitted|invalid api key|authentication)\b", re.I)
_VALIDATION_TEXT = re.compile(r"\b(invalid|malformed|missing required|schema|bad request|must be)\b", re.I)
_PERMANENT_TEXT = re.compile(r"\b(not found|does not exist|no such|already exists|conflict)\b", re.I)


def classify_error(error: object) -> ToolError:
    """Best-effort classification of an arbitrary raised value. Prefer raising a
    ClassifiedError from tools/providers where the type is known; this heuristic is the
    fallback for raw SDK errors. Conservative by design: only clear transient signals become
    retryable, so an unknown error defaults to permanent (surface-as-final) rather than
    looping."""
    if isinstance(error, ClassifiedError):
        return ToolError(type=error.type, message=str(error), code=error.code, retryable=error.type == "transient")

    message = str(error)
    status = _extract_status(error)
    haystack = f"{status if status is not None else ''} {message}"

    is_transient_status = status == 429 or (status is not None and status >= 500)
    is_transient_text = bool(_TRANSIENT_CODE.search(haystack) or _TRANSIENT_TEXT.search(haystack))
    if status in (401, 403) or _AUTH_TEXT.search(haystack):
        error_type: ToolErrorType = "auth"
    elif is_transient_status or is_transient_text:
        error_type = "transient"
    elif status in (400, 422) or _VALIDATION_TEXT.search(haystack):
        error_type = "validation"
    elif status in (404, 409) or _PERMANENT_TEXT.search(haystack):
        error_type = "permanent"
    else:
        error_type = "permanent"

    return ToolError(
        type=error_type,
        message=message,
        code=str(status) if isinstance(status, int) else None,
        retryable=error_type == "transient",
    )


def _extract_status(error: object) -> int | None:
    for attr in ("status", "status_code", "code"):
        value = getattr(error, attr, None)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r"\d{3}", value):
            return int(value)
    return None
