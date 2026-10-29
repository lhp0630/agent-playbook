"""Unit tests for OpenSandbox capability configuration. No live server."""

import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.workspaces import WorkspaceRef

from harness.open_sandbox import OpenSandbox, OpenSandboxBackend
from harness.open_sandbox._backend import DEFAULT_IMAGE, DEFAULT_SANDBOX_TIMEOUT, PROVIDER


def test_owned_defaults_build_a_backend_without_io():
    cap = OpenSandbox()
    backend = cap.get_workspace(None, ref=None)  # type: ignore[arg-type]
    assert cap.image == DEFAULT_IMAGE
    assert cap.sandbox_timeout == DEFAULT_SANDBOX_TIMEOUT
    assert cap.volumes is None
    assert isinstance(backend, OpenSandboxBackend)
    assert backend.ref is None
    assert backend._volumes is None  # pyright: ignore[reportPrivateUsage]


def test_passes_compose_volumes_to_the_backend():
    cap = OpenSandbox(volumes=["data:/var/lib/data"])
    backend = cap.get_workspace(None, ref=None)  # type: ignore[arg-type]
    assert isinstance(backend, OpenSandboxBackend)
    assert backend._volumes == ["data:/var/lib/data"]  # pyright: ignore[reportPrivateUsage]


def test_rejects_host_bind_volumes():
    with pytest.raises(ValueError, match="host path"):
        OpenSandbox(volumes=["/host/data:/var/lib/data"])


def test_get_workspace_ignores_a_foreign_provider():
    ref = WorkspaceRef(provider="e2b", id="sbx-1")
    assert OpenSandbox().get_workspace(None, ref=ref) is None  # type: ignore[arg-type]


def test_get_workspace_attaches_to_an_opensandbox_ref():
    ref = WorkspaceRef(provider=PROVIDER, id="sbx-1")
    backend = OpenSandbox().get_workspace(None, ref=ref)  # type: ignore[arg-type]
    assert isinstance(backend, OpenSandboxBackend)
    assert backend.ref == ref


def test_backend_helper_rejects_a_foreign_provider():
    ref = WorkspaceRef(provider="e2b", id="sbx-1")
    with pytest.raises(ValueError, match="opensandbox"):
        OpenSandbox().backend(ref)


def test_rejects_non_positive_timeout_and_relative_working_dir():
    with pytest.raises(ValueError, match="sandbox_timeout"):
        OpenSandbox(sandbox_timeout=0)
    with pytest.raises(ValueError, match="working_dir"):
        OpenSandbox(working_dir="relative")


def test_rejects_defer_loading():
    with pytest.raises(UserError, match="defer_loading"):
        OpenSandbox(defer_loading=True)


def test_rejects_non_string_env():
    with pytest.raises(UserError, match="env"):
        OpenSandbox(env={"PATH": 1})  # type: ignore[dict-item]
