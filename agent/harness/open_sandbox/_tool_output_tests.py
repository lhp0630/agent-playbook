"""Unit tests for OpenSandbox output helpers (no live sandbox)."""

import pytest
from pydantic_ai.exceptions import ModelRetry

from agent.harness.open_sandbox._tool_output import (
    guard_read_size,
    render_file_window,
    truncate_output,
)


def test_truncate_output_keeps_tail_and_marks_cut():
    text = "\n".join(f"line-{i}" for i in range(10))
    out = truncate_output(text, max_lines=3, max_bytes=10_000, direction="tail")
    assert "line-9" in out
    assert "line-0" not in out
    assert "truncated" in out


def test_truncate_output_keeps_head_for_listings():
    text = "\n".join(f"entry-{i}" for i in range(10))
    out = truncate_output(text, max_lines=3, max_bytes=10_000, direction="head")
    assert out.startswith("entry-0")
    assert "entry-9" not in out
    assert "truncated" in out


def test_guard_read_size_refuses_oversized_file():
    with pytest.raises(ModelRetry, match="read limit"):
        guard_read_size(1024, max_bytes=100)


def test_render_file_window_pages_with_offset():
    data = b"\n".join(f"L{i}".encode() for i in range(1, 6))
    out = render_file_window(data, offset=2, limit=2, max_lines=100, max_bytes=10_000)
    assert "L2" in out
    assert "L3" in out
    assert "offset=4" in out
