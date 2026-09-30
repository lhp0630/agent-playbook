"""OpenSandbox toolset: gives agents a container sandbox to work in."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.tools import AgentDepsT
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset
from typing_extensions import Self

from agent.harness.open_sandbox._session import (
    OpenSandboxError,
    OpenSandboxSession,
    OpenSandboxTerminalError,
)
from agent.harness.open_sandbox._tool_output import (
    guard_read_size,
    render_file_window,
    truncate_output,
)


class OpenSandboxToolset(FunctionToolset[AgentDepsT]):
    """Gives an agent an OpenSandbox to run commands and manage files in."""

    def __init__(
        self,
        *,
        image: str,
        sandbox_id: str | None,
        sandbox_timeout: int,
        workdir: str | None,
        default_command_timeout: float,
        max_command_timeout: int | None,
        max_output_bytes: int,
        max_output_lines: int,
        max_read_bytes: int,
        env: Mapping[str, str] | None = None,
        session: OpenSandboxSession | None = None,
        _run_scoped: bool = False,
    ) -> None:
        super().__init__()
        self._image = image
        self._sandbox_id = sandbox_id
        self._sandbox_timeout = sandbox_timeout
        self._workdir = workdir
        self._default_command_timeout = default_command_timeout
        self._max_command_timeout = max_command_timeout
        self._max_output_bytes = max_output_bytes
        self._max_output_lines = max_output_lines
        self._max_read_bytes = max_read_bytes
        self._env = dict(env) if env is not None else None
        self._external_session = session
        self._session: OpenSandboxSession | None = None
        self._run_scoped = _run_scoped

        self.add_function(self.run_command, name="run_command")
        self.add_function(self.read_file, name="read_file")
        self.add_function(self.write_file, name="write_file")
        self.add_function(self.list_directory, name="list_directory")

    async def for_run(self, ctx: RunContext[AgentDepsT]) -> AbstractToolset[AgentDepsT]:
        return OpenSandboxToolset[AgentDepsT](
            image=self._image,
            sandbox_id=self._sandbox_id,
            sandbox_timeout=self._sandbox_timeout,
            workdir=self._workdir,
            default_command_timeout=self._default_command_timeout,
            max_command_timeout=self._max_command_timeout,
            max_output_bytes=self._max_output_bytes,
            max_output_lines=self._max_output_lines,
            max_read_bytes=self._max_read_bytes,
            env=self._env,
            session=self._external_session,
            _run_scoped=True,
        )

    async def __aenter__(self) -> Self:
        if not self._run_scoped:
            return self
        if self._external_session is not None:
            if self._external_session.sandbox_id is None:
                raise OpenSandboxError(
                    "The injected session is not open. Enter it with `async with session:` "
                    "before running the agent."
                )
            self._session = self._external_session
            return self
        session = OpenSandboxSession(
            image=self._image,
            sandbox_id=self._sandbox_id,
            sandbox_timeout=self._sandbox_timeout,
            workdir=self._workdir,
            env=self._env,
        )
        await session.__aenter__()
        self._session = session
        return self

    async def __aexit__(self, *args: object) -> None:
        session = self._session
        self._session = None
        if session is not None and self._external_session is None:
            await session.__aexit__(*args)

    def _require_session(self) -> OpenSandboxSession:
        if self._session is None:
            raise OpenSandboxError("The OpenSandbox session is not open.")
        return self._session

    def _truncate_stream(self, text: str, already_truncated: bool) -> str:
        return truncate_output(
            text,
            max_lines=self._max_output_lines,
            max_bytes=self._max_output_bytes,
            direction="tail",
            already_truncated=already_truncated,
        )

    def _command_timeout(self, timeout_seconds: float | None) -> int:
        if timeout_seconds is not None and (
            not math.isfinite(timeout_seconds) or timeout_seconds <= 0
        ):
            raise ModelRetry(f"timeout_seconds must be greater than 0, got {timeout_seconds}.")
        requested = (
            timeout_seconds if timeout_seconds is not None else self._default_command_timeout
        )
        ceiling = (
            self._max_command_timeout
            if self._max_command_timeout is not None
            else self._sandbox_timeout
        )
        return min(max(1, math.ceil(requested)), ceiling)

    async def run_command(self, command: str, *, timeout_seconds: float | None = None) -> str:
        """Run a shell command in the sandbox and return its output."""
        session = self._require_session()
        try:
            result = await session.exec(
                ["sh", "-c", command],
                timeout=self._command_timeout(timeout_seconds),
                max_output_bytes=self._max_output_bytes,
            )
        except OpenSandboxTerminalError:
            raise
        except OpenSandboxError as e:
            raise ModelRetry(str(e)) from None
        parts: list[str] = []
        if result.stdout:
            parts.append(
                f"[stdout]\n{self._truncate_stream(result.stdout, result.stdout_truncated)}"
            )
        if result.stderr:
            parts.append(
                f"[stderr]\n{self._truncate_stream(result.stderr, result.stderr_truncated)}"
            )
        output = "\n".join(parts) if parts else "(no output)"
        if result.timed_out:
            return f"{output}\n[timed out after {result.applied_timeout}s]"
        if result.returncode:
            return f"{output}\n[exit code: {result.returncode}]"
        return output

    async def read_file(
        self,
        path: str,
        *,
        offset: Annotated[
            int | None, Field(description="Line number to start reading from (1-indexed)")
        ] = None,
        limit: Annotated[int | None, Field(description="Maximum number of lines to read")] = None,
    ) -> str:
        """Read a text file from the sandbox and return its contents."""
        session = self._require_session()
        try:
            guard_read_size(await session.file_size(path), max_bytes=self._max_read_bytes)
            data = await session.read_bytes(path)
        except OpenSandboxTerminalError:
            raise
        except OpenSandboxError as e:
            raise ModelRetry(f"Could not read {path!r}: {e}") from None
        guard_read_size(len(data), max_bytes=self._max_read_bytes)
        return render_file_window(
            data,
            offset=offset,
            limit=limit,
            max_lines=self._max_output_lines,
            max_bytes=self._max_output_bytes,
        )

    async def write_file(self, path: str, content: str) -> str:
        """Write text to a file in the sandbox, creating parent directories."""
        session = self._require_session()
        try:
            data = content.encode("utf-8")
        except UnicodeEncodeError:
            raise ModelRetry(
                "content contains characters that cannot be encoded as UTF-8 (unpaired surrogates)."
            ) from None
        try:
            await session.write_bytes(path, data)
        except OpenSandboxTerminalError:
            raise
        except OpenSandboxError as e:
            raise ModelRetry(f"Could not write {path!r}: {e}") from None
        return f"Wrote {len(data)} bytes to {path!r}."

    async def list_directory(self, path: str = ".") -> str:
        """List the entries in a sandbox directory (directories shown with a trailing `/`)."""
        session = self._require_session()
        try:
            entries = await session.list_files(path)
        except OpenSandboxTerminalError:
            raise
        except OpenSandboxError as e:
            raise ModelRetry(f"Could not list {path!r}: {e}") from None
        if not entries:
            return "(empty)"
        names = [f"{name}/" if is_dir else name for name, is_dir in sorted(entries)]
        return truncate_output(
            "\n".join(names),
            max_lines=self._max_output_lines,
            max_bytes=self._max_output_bytes,
            direction="head",
        )
