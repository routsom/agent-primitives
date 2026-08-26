from multiagent_boilerplate.agents.review import ReviewSignals, derive_review_flags
from multiagent_boilerplate.harness.errors import ToolError

TRANSIENT = ToolError(type="transient", message="x", retryable=True)
AUTH = ToolError(type="auth", message="x", retryable=False)


def test_clean_ok_run_needs_no_review() -> None:
    flags = derive_review_flags(
        ReviewSignals(
            status="ok",
            unrecovered_errors=[],
            final_text="A perfectly reasonable answer.",
            last_stop_reason="end_turn",
        )
    )
    assert flags == []


def test_flags_partial_completion() -> None:
    flags = derive_review_flags(ReviewSignals(status="partial", unrecovered_errors=[], final_text="stopped"))
    assert "partial_completion" in flags


def test_flags_each_distinct_error_type_once() -> None:
    flags = derive_review_flags(
        ReviewSignals(
            status="ok",
            unrecovered_errors=[TRANSIENT, TRANSIENT, AUTH],
            final_text="a sufficiently long answer here",
        )
    )
    assert "unrecovered_tool_error:transient" in flags
    assert "unrecovered_tool_error:auth" in flags
    assert flags.count("unrecovered_tool_error:transient") == 1


def test_flags_max_tokens_truncation() -> None:
    flags = derive_review_flags(
        ReviewSignals(
            status="ok",
            unrecovered_errors=[],
            final_text="a sufficiently long answer here",
            last_stop_reason="max_tokens",
        )
    )
    assert "max_tokens_truncation" in flags


def test_flags_empty_ok_response() -> None:
    flags = derive_review_flags(
        ReviewSignals(status="ok", unrecovered_errors=[], final_text="  ok  ", last_stop_reason="end_turn")
    )
    assert "empty_response" in flags
