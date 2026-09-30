"""Unit tests for OpenSandboxSession helpers that need no live server."""

from types import SimpleNamespace

import pytest

from agent.harness.open_sandbox._session import (
    OpenSandboxSession,
    _classify_execution,
    _tail_bytes_text,
)


def test_session_attach_rejects_owned_settings():
    with pytest.raises(ValueError, match="image"):
        OpenSandboxSession(sandbox_id="sbx-1", image="python:3.12-slim")


def test_session_rejects_non_positive_timeout():
    with pytest.raises(ValueError, match="sandbox_timeout"):
        OpenSandboxSession(sandbox_timeout=0)


def test_tail_bytes_text_marks_truncation():
    text, truncated = _tail_bytes_text("abcdefghij", max_bytes=4)
    assert truncated is True
    assert text.encode("utf-8") == b"ghij"


def test_tail_bytes_text_passthrough_when_under_cap():
    text, truncated = _tail_bytes_text("hi", max_bytes=10)
    assert text == "hi"
    assert truncated is False


def test_classify_missing_exit_code_is_failure_not_timeout():
    # Symptom regression: a deadline + missing exit_code used to report timed_out,
    # so the model lengthened the timeout instead of fixing the real error.
    returncode, timed_out, note = _classify_execution(exit_code=None, error=None, deadline=60)
    assert returncode == 1
    assert timed_out is False
    assert note is None


def test_classify_generic_execution_error_is_failure_not_timeout():
    error = SimpleNamespace(name="RuntimeError", value="boom")
    returncode, timed_out, note = _classify_execution(exit_code=None, error=error, deadline=60)
    assert returncode == 1
    assert timed_out is False
    assert note == "RuntimeError: boom"


def test_classify_timeout_exit_codes_when_deadline_set():
    _, timed_out_neg, _ = _classify_execution(exit_code=-1, error=None, deadline=30)
    _, timed_out_kill, _ = _classify_execution(exit_code=137, error=None, deadline=30)
    assert timed_out_neg is True
    assert timed_out_kill is True


def test_classify_timeout_error_name_when_deadline_set():
    error = SimpleNamespace(name="TimeoutError", value="command exceeded limit")
    returncode, timed_out, note = _classify_execution(exit_code=None, error=error, deadline=30)
    assert timed_out is True
    assert returncode == 1
    assert note is not None and "TimeoutError" in note


def test_classify_normal_nonzero_exit_not_timeout():
    returncode, timed_out, _ = _classify_execution(exit_code=2, error=None, deadline=60)
    assert returncode == 2
    assert timed_out is False


def test_classify_without_deadline_never_times_out():
    _, timed_out, _ = _classify_execution(exit_code=-1, error=None, deadline=None)
    assert timed_out is False
