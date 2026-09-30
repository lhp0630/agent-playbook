"""Unit tests for OpenSandbox capability configuration and instructions."""

import pytest

from agent.harness.open_sandbox import OpenSandbox, OpenSandboxSession
from agent.harness.open_sandbox._session import DEFAULT_IMAGE, DEFAULT_SANDBOX_TIMEOUT


def test_owned_defaults_and_instructions():
    cap = OpenSandbox()
    assert cap.image == DEFAULT_IMAGE
    assert cap.sandbox_timeout == DEFAULT_SANDBOX_TIMEOUT
    instructions = cap.get_instructions()
    assert instructions is not None
    assert "ephemeral" in instructions
    assert "run_command" in instructions
    assert "60s" in instructions


def test_attached_instructions_mention_persistence():
    cap = OpenSandbox(sandbox_id="sbx-1")
    instructions = cap.get_instructions()
    assert instructions is not None
    assert "persists across runs" in instructions


def test_custom_instructions_override_and_empty_disables():
    assert OpenSandbox(instructions="Use the box.").get_instructions() == "Use the box."
    assert OpenSandbox(instructions="").get_instructions() is None


def test_session_rejects_sandbox_id_and_owned_settings():
    session = OpenSandboxSession()
    with pytest.raises(ValueError, match="session"):
        OpenSandbox(session=session, sandbox_id="sbx-1")
    with pytest.raises(ValueError, match="image"):
        OpenSandbox(session=session, image="python:3.12-slim")


def test_attach_rejects_owned_settings():
    with pytest.raises(ValueError, match="image"):
        OpenSandbox(sandbox_id="sbx-1", image="python:3.12-slim")
    with pytest.raises(ValueError, match="sandbox_timeout"):
        OpenSandbox(sandbox_id="sbx-1", sandbox_timeout=600)


def test_owned_rejects_command_ceiling_above_sandbox_lifetime():
    with pytest.raises(ValueError, match="max_command_timeout"):
        OpenSandbox(sandbox_timeout=60, max_command_timeout=120)


def test_rejects_non_positive_limits():
    with pytest.raises(ValueError, match="sandbox_timeout"):
        OpenSandbox(sandbox_timeout=0)
    with pytest.raises(ValueError, match="default_command_timeout"):
        OpenSandbox(default_command_timeout=-1)


def test_get_toolset_builds_open_sandbox_toolset():
    from agent.harness.open_sandbox._toolset import OpenSandboxToolset

    toolset = OpenSandbox().get_toolset()
    assert isinstance(toolset, OpenSandboxToolset)
