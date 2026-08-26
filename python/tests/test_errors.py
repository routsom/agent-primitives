from multiagent_boilerplate.harness.errors import (
    AuthFailure,
    ClassifiedError,
    ValidationFailure,
    classify_error,
)


def test_honors_explicit_classification_and_derives_retryable() -> None:
    assert classify_error(ClassifiedError("transient", "boom")).retryable is True
    assert classify_error(ValidationFailure("bad input")).type == "validation"
    assert classify_error(ValidationFailure("bad input")).retryable is False
    assert classify_error(AuthFailure("nope")).type == "auth"


class _StatusError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def test_classifies_status_bearing_errors() -> None:
    assert classify_error(_StatusError(429, "slow down")).type == "transient"
    assert classify_error(_StatusError(503, "down")).type == "transient"
    assert classify_error(_StatusError(401, "no")).type == "auth"
    assert classify_error(_StatusError(422, "bad")).type == "validation"
    assert classify_error(_StatusError(404, "gone")).type == "permanent"


def test_classifies_from_message_text() -> None:
    assert classify_error(Exception("Connection reset by peer")).type == "transient"
    assert classify_error(Exception("rate limit exceeded")).type == "transient"
    assert classify_error(Exception("permission denied")).type == "auth"


def test_unknown_error_defaults_to_permanent() -> None:
    classified = classify_error(Exception("something unexpected happened"))
    assert classified.type == "permanent"
    assert classified.retryable is False


def test_only_transient_is_retryable() -> None:
    for error_type in ("permanent", "validation", "auth"):
        assert classify_error(ClassifiedError(error_type, "x")).retryable is False
    assert classify_error(ClassifiedError("transient", "x")).retryable is True
