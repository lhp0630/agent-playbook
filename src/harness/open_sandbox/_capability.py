"""OpenSandbox capability: isolated container workspace for an agent run."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    """Supply an OpenSandbox container as the run's workspace, created on first use.

    A run with no reference creates a fresh sandbox. Pass a
    [`WorkspaceRef`][pydantic_ai.workspaces.WorkspaceRef] supplied by the application to
    attach to one from an earlier run. The sandbox outlives the run: remove it with
    [`destroy`][harness.open_sandbox.OpenSandbox.destroy].

    This capability supplies execution only. Compose it with tools that use the workspace,
    such as [`Shell`][pydantic_ai_harness.shell.Shell] or
    [`FileSystem`][pydantic_ai_harness.filesystem.FileSystem]. Requires the `opensandbox`
    package and a reachable server via `OPEN_SANDBOX_API_KEY` / `OPEN_SANDBOX_DOMAIN`.

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
    """OCI image for a newly created sandbox, such as `'opensandbox/code-interpreter:v1.1.0'`.

    It needs a POSIX `sh` and the usual file utilities.
    """

    sandbox_timeout: int = DEFAULT_SANDBOX_TIMEOUT
    """Seconds a newly created sandbox may go unused before the server shuts it down.

    Every operation renews it as it starts, so a single command must finish within it.
    """

    working_dir: str | None = None
    """Absolute directory commands start in and relative paths resolve against.

    Created on first use if missing. `None` uses the container's own directory. Applies to
    attached sandboxes too.
    """

    env: Mapping[str, str] | None = field(default=None, repr=False)
    """Environment variables every command gets, also on an attached sandbox.

    Nothing is read from the host.
    """

    volumes: Sequence[str] | None = None
    """Compose short-syntax mounts for a new sandbox.

    For example `'data:/var/lib/data'` or `'cache:/cache:ro'`. Named PVC only; host binds
    and remote URIs are rejected. `None` mounts nothing. Ignored when attaching by ref.
    """

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
        """Attach lazily to an existing sandbox by ref."""
        if ref.provider != PROVIDER:
            raise ValueError(
                f"unsupported workspace provider {ref.provider!r}; expected {PROVIDER!r}"
            )
        return self._new_backend(ref)

    async def destroy(self, ref: WorkspaceRef) -> None:
        """Destroy a sandbox by ref. One that is already gone returns quietly."""
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
            volumes=self.volumes,
        )
