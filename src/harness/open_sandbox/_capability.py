"""Capability that supplies an OpenSandbox container as an agent run's workspace."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import UserError
from pydantic_ai.tools import AgentDepsT, RunContext
from pydantic_ai.workspaces import WorkspaceBackend, WorkspaceRef

from harness.open_sandbox._backend import (
    DEFAULT_IMAGE,
    DEFAULT_SANDBOX_TIMEOUT,
    PROVIDER,
    OpenSandboxBackend,
    _check_env,
    _check_positive_int,
    _check_working_dir,
    destroy_sandbox,
)


@dataclass(kw_only=True)
class OpenSandbox(AbstractCapability[AgentDepsT]):
    """Supply an isolated OpenSandbox container as the run's workspace.

    A run with no reference creates a fresh container on first use. Pass a ``WorkspaceRef``
    supplied by the application to attach to a sandbox from an earlier run.

    This capability supplies execution only. Compose it with tools or capabilities that
    use the workspace, such as ``Shell`` or ``FileSystem``. Commands and file operations
    run inside the container through ``ctx.workspace``.

    Requires the ``opensandbox`` package and a reachable OpenSandbox server configured
    via ``OPEN_SANDBOX_API_KEY`` / ``OPEN_SANDBOX_DOMAIN``.

    ```python
    from pydantic_ai import Agent
    from pydantic_ai_harness.filesystem import FileSystem
    from pydantic_ai_harness.shell import Shell
    from harness.open_sandbox import OpenSandbox

    agent = Agent(
        'openai:ornith:35b',
        capabilities=[OpenSandbox(), Shell(), FileSystem()],
    )
    ```
    """

    image: str = DEFAULT_IMAGE
    """OCI image for a newly created sandbox."""

    sandbox_timeout: int = DEFAULT_SANDBOX_TIMEOUT
    """Lifetime in seconds of a newly created sandbox before the server shuts it down."""

    working_dir: str | None = None
    """Absolute directory commands start in and relative paths resolve against.

    ``None`` uses the container's own directory. Created when this capability creates
    the sandbox.
    """

    env: Mapping[str, str] | None = field(default=None, repr=False)
    """Environment variables every command gets. Nothing is read from the host."""

    def __post_init__(self) -> None:
        if self.defer_loading:
            raise UserError(
                "`OpenSandbox` does not support `defer_loading=True`: "
                "the workspace is selected before deferred capabilities load."
            )
        _check_positive_int("sandbox_timeout", self.sandbox_timeout)
        _check_working_dir(self.working_dir)
        try:
            checked = _check_env(self.env)
        except ValueError as error:
            raise UserError(str(error)) from None
        if checked is not None:
            self.env = checked
        # Fail a bad option when the agent is defined, before the first run.
        self._new_backend(None)

    def backend(self, ref: WorkspaceRef) -> OpenSandboxBackend:
        """Attach lazily to an existing sandbox."""
        if ref.provider != PROVIDER:
            raise ValueError(
                f"unsupported workspace provider {ref.provider!r}; expected {PROVIDER!r}"
            )
        return self._new_backend(ref)

    async def destroy(self, ref: WorkspaceRef) -> None:
        """Kill a sandbox by ref. One that is already gone returns quietly."""
        if ref.provider != PROVIDER:
            raise ValueError(
                f"unsupported workspace provider {ref.provider!r}; expected {PROVIDER!r}"
            )
        await destroy_sandbox(ref.id)

    def get_workspace(
        self, ctx: RunContext[AgentDepsT], *, ref: WorkspaceRef | None
    ) -> WorkspaceBackend | None:
        """Build the backend for this run. No I/O here: it creates or attaches on first use."""
        del ctx
        if ref is not None and ref.provider != PROVIDER:
            return None
        return self._new_backend(ref)

    def _new_backend(self, ref: WorkspaceRef | None) -> OpenSandboxBackend:
        return OpenSandboxBackend(
            ref=ref,
            image=self.image,
            sandbox_timeout=self.sandbox_timeout,
            working_dir=self.working_dir,
            env=self.env,
        )
