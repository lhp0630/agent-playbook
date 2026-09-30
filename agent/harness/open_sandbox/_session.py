"""Lifecycle management for an OpenSandbox container."""

from __future__ import annotations

import math
import posixpath
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import anyio
import anyio.lowlevel
from typing_extensions import Self

if TYPE_CHECKING:
    from opensandbox import Sandbox

# Defaults shared by `OpenSandboxSession` and `OpenSandbox` so "left at default"
# checks cannot drift between the two constructors.
DEFAULT_IMAGE = "opensandbox/code-interpreter:v1.1.0"
DEFAULT_SANDBOX_TIMEOUT = 300

_MISSING_OPENSANDBOX = (
    "The 'opensandbox' package is required for OpenSandbox. "
    'Install it with `uv add "pydantic-ai-skills[opensandbox]"`.'
)
_AUTH_MESSAGE = (
    "OpenSandbox rejected the credentials. Set OPEN_SANDBOX_API_KEY "
    "(and OPEN_SANDBOX_DOMAIN if not using the default server)."
)

# Bound create/connect so a wedged control plane cannot hang enter forever.
_CREATE_TIMEOUT = 120
_TEARDOWN_TIMEOUT = 30
_INTERNAL_EXEC_TIMEOUT = 10


class OpenSandboxError(RuntimeError):
    """Base class for failures reported by the OpenSandbox integration.

    The toolset turns direct instances into `ModelRetry`. Terminal subclasses
    propagate because retrying cannot restore a missing sandbox or credentials.
    """


class OpenSandboxTerminalError(OpenSandboxError):
    """A sandbox failure that retrying cannot fix, so the run should end."""


class OpenSandboxUnavailableError(OpenSandboxTerminalError):
    """The sandbox no longer exists: killed, or expired at its `sandbox_timeout`."""


class OpenSandboxAuthError(OpenSandboxTerminalError):
    """OpenSandbox rejected the credentials, so no sandbox operation can succeed."""


@dataclass(frozen=True, kw_only=True)
class OpenSandboxExecResult:
    """The outcome of running a command in the sandbox."""

    stdout: str
    stderr: str
    returncode: int
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timed_out: bool = False
    applied_timeout: int | None = None


def _require_opensandbox() -> Any:
    try:
        from opensandbox import Sandbox as sandbox_cls
    except ImportError as exc:
        raise OpenSandboxError(_MISSING_OPENSANDBOX) from exc
    return sandbox_cls


def _is_auth_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return True
    name = type(exc).__name__.lower()
    return "auth" in name or "unauthorized" in name or "forbidden" in name


def _is_unavailable_error(exc: BaseException) -> bool:
    from opensandbox.exceptions import (
        SandboxTimeoutException,
        SandboxUnhealthyException,
    )

    if isinstance(exc, (SandboxTimeoutException, SandboxUnhealthyException)):
        return True
    status = getattr(exc, "status_code", None)
    return status == 404


class OpenSandboxSession:
    """Async context manager that owns or attaches to an OpenSandbox container.

    In *owned* mode (the default) it creates a fresh sandbox from `image` on enter
    and destroys it on exit. In *attach* mode (`sandbox_id` set) it connects to an
    existing sandbox and leaves it running on exit.

    Backed by [`opensandbox.Sandbox`](https://github.com/opensandbox-group/OpenSandbox),
    the same SDK used by
    [`OpenSandboxScriptExecutor`][pydantic_ai_skills.sandboxes.opensandbox.OpenSandboxScriptExecutor].
    Configure the server via `OPEN_SANDBOX_API_KEY` / `OPEN_SANDBOX_DOMAIN`.
    """

    def __init__(
        self,
        *,
        image: str = DEFAULT_IMAGE,
        sandbox_id: str | None = None,
        sandbox_timeout: int = DEFAULT_SANDBOX_TIMEOUT,
        workdir: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if type(sandbox_timeout) is not int or sandbox_timeout <= 0:
            raise ValueError(
                f"sandbox_timeout must be a positive integer, got {sandbox_timeout!r}."
            )
        if sandbox_id is not None:
            conflicts = [
                name
                for name, value, default in (
                    ("image", image, DEFAULT_IMAGE),
                    ("sandbox_timeout", sandbox_timeout, DEFAULT_SANDBOX_TIMEOUT),
                    ("workdir", workdir, None),
                    ("env", env, None),
                )
                if value != default
            ]
            if conflicts:
                raise ValueError(
                    f"{', '.join(conflicts)} only apply when creating a sandbox, "
                    "but `sandbox_id` attaches to an existing one. "
                    "Remove them, or drop `sandbox_id` to create a sandbox."
                )
        self._image = image
        self._sandbox_id = sandbox_id
        self._sandbox_timeout = sandbox_timeout
        self._workdir = workdir
        self._env = dict(env) if env is not None else None
        self._sandbox: Sandbox | None = None
        self._cwd: str | None = None
        self._cwd_lock = anyio.Lock()

    @property
    def sandbox_id(self) -> str | None:
        """The id of the running sandbox, or None when it is not running."""
        if self._sandbox is None:
            return None
        return self._sandbox.id

    async def __aenter__(self) -> Self:
        if self._sandbox is not None:
            raise OpenSandboxError(
                "The session is already open; exit it before entering again. "
                "Use a separate session per concurrent context."
            )
        self._cwd = None
        sandbox_cls = _require_opensandbox()
        try:
            with anyio.CancelScope(shield=True):
                with anyio.move_on_after(_CREATE_TIMEOUT):
                    self._sandbox = await self._open_sandbox(sandbox_cls)
        except OpenSandboxError:
            raise
        except Exception as e:
            raise self._open_error(e) from e
        if self._sandbox is None:
            raise OpenSandboxError(
                f"OpenSandbox creation did not complete within {_CREATE_TIMEOUT}s; "
                "the OpenSandbox control plane may be unreachable."
            )
        try:
            await anyio.lowlevel.checkpoint()
        except BaseException:
            await self.__aexit__(None, None, None)
            raise
        return self

    async def _open_sandbox(self, sandbox_cls: Any) -> Sandbox:
        if self._sandbox_id is not None:
            return await sandbox_cls.connect(self._sandbox_id)
        return await sandbox_cls.create(
            self._image,
            env=self._env,
            timeout=timedelta(seconds=self._sandbox_timeout),
        )

    async def __aexit__(self, *args: object) -> None:
        sandbox = self._sandbox
        self._sandbox = None
        self._cwd = None
        if sandbox is None:
            return
        owned = self._sandbox_id is None
        with anyio.CancelScope(shield=True):
            with anyio.move_on_after(_TEARDOWN_TIMEOUT):
                try:
                    if owned:
                        await sandbox.destroy()
                    else:
                        await sandbox.close()
                except Exception:
                    pass

    def _require_sandbox(self) -> Sandbox:
        sandbox = self._sandbox
        if sandbox is None:
            raise OpenSandboxError(
                "The sandbox is not running; use the session as an async context manager."
            )
        return sandbox

    def _unavailable_message(self) -> str:
        if self._sandbox_id is not None:
            return (
                f"The attached OpenSandbox {self._sandbox_id!r} is no longer running "
                "(killed, or expired at its configured lifetime). "
                "Attach to a live sandbox, or create a new one."
            )
        return (
            "The OpenSandbox is no longer running (it may have reached its "
            f"sandbox_timeout of {self._sandbox_timeout}s, or been killed). "
            "Start a new run, or raise sandbox_timeout for longer work."
        )

    def _open_error(self, e: Exception) -> OpenSandboxError:
        if _is_auth_error(e):
            return OpenSandboxAuthError(_AUTH_MESSAGE)
        if self._sandbox_id is not None and _is_unavailable_error(e):
            return OpenSandboxUnavailableError(
                f"Could not attach to OpenSandbox {self._sandbox_id!r}: "
                "it does not exist or has terminated."
            )
        return OpenSandboxError(f"Could not start OpenSandbox: {e}")

    def _map_error(self, e: Exception, context: str) -> OpenSandboxError:
        if _is_auth_error(e):
            return OpenSandboxAuthError(_AUTH_MESSAGE)
        if _is_unavailable_error(e):
            return OpenSandboxUnavailableError(self._unavailable_message())
        return OpenSandboxError(f"{context}: {e}")

    async def _resolve(self, path: str) -> str:
        """Resolve a possibly-relative path against the sandbox working directory."""
        if posixpath.isabs(path):
            return path
        if self._cwd is None:
            async with self._cwd_lock:
                if self._cwd is None:
                    if self._workdir is not None:
                        self._cwd = self._workdir
                    else:
                        result = await self.exec(
                            ["sh", "-c", "pwd"], timeout=_INTERNAL_EXEC_TIMEOUT
                        )
                        if result.returncode != 0:
                            raise OpenSandboxError(
                                "Could not determine the sandbox working directory to resolve a "
                                f"relative path ({path!r}); use an absolute path or retry."
                            )
                        self._cwd = result.stdout.strip() or "/"
        if path in ("", "."):
            return self._cwd
        return posixpath.join(self._cwd, path)

    async def exec(
        self,
        argv: Sequence[str],
        *,
        timeout: float | None = None,
        max_output_bytes: int | None = None,
    ) -> OpenSandboxExecResult:
        """Run an argument vector in the sandbox and return its result."""
        sandbox = self._require_sandbox()
        if isinstance(argv, str):
            raise TypeError(f"argv must be a sequence of arguments, not a string; got {argv!r}.")
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError(f"timeout must be a positive finite number or None, got {timeout!r}.")
        if max_output_bytes is not None and (
            type(max_output_bytes) is not int or max_output_bytes <= 0
        ):
            raise ValueError(
                f"max_output_bytes must be a positive integer or None, got {max_output_bytes!r}."
            )

        from opensandbox.models.execd import RunCommandOpts

        deadline = None if timeout is None else max(1, math.ceil(timeout))
        # OpenSandbox accepts shell text or argv; join safely for sh -c style callers
        # that pass ['sh', '-c', command] while also supporting bare argv.
        if len(argv) >= 3 and argv[0] == "sh" and argv[1] == "-c":
            command: str | list[str] = argv[2]
        else:
            command = list(argv)

        opts = RunCommandOpts(
            working_directory=self._workdir,
            timeout=timedelta(seconds=deadline) if deadline is not None else None,
            envs=self._env,
        )
        try:
            execution = await sandbox.commands.run(command, opts=opts)
        except Exception as e:
            raise self._map_error(e, "Command could not run in the sandbox") from e

        stdout = "".join(message.text for message in execution.logs.stdout)
        stderr = "".join(message.text for message in execution.logs.stderr)
        stdout_truncated = False
        stderr_truncated = False
        if max_output_bytes is not None:
            stdout, stdout_truncated = _tail_bytes_text(stdout, max_output_bytes)
            stderr, stderr_truncated = _tail_bytes_text(stderr, max_output_bytes)

        returncode, timed_out, error_note = _classify_execution(
            exit_code=execution.exit_code,
            error=execution.error,
            deadline=deadline,
        )
        # Surface SDK execution errors in stderr so the model sees the real failure
        # instead of only a misleading timeout label.
        if error_note:
            stderr = f"{stderr}\n{error_note}" if stderr else error_note

        return OpenSandboxExecResult(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            timed_out=timed_out,
            applied_timeout=deadline,
        )

    async def file_size(self, path: str) -> int:
        sandbox = self._require_sandbox()
        target = await self._resolve(path)
        try:
            infos = await sandbox.files.get_file_info([target])
        except Exception as e:
            raise self._map_error(e, f"Could not stat {path!r}") from e
        info = infos.get(target)
        if info is None:
            raise OpenSandboxError(f"Could not stat {path!r}: no metadata returned.")
        return info.size

    async def read_bytes(self, path: str) -> bytes:
        sandbox = self._require_sandbox()
        target = await self._resolve(path)
        try:
            return await sandbox.files.read_bytes(target)
        except Exception as e:
            raise self._map_error(e, f"Could not read {path!r}") from e

    async def write_bytes(self, path: str, data: bytes) -> None:
        sandbox = self._require_sandbox()
        target = await self._resolve(path)
        try:
            parent = posixpath.dirname(target)
            if parent and parent != "/":
                from opensandbox.models.filesystem import WriteEntry

                await sandbox.files.create_directories([WriteEntry(path=parent)])
            await sandbox.files.write_file(target, data)
        except Exception as e:
            raise self._map_error(e, f"Could not write {path!r}") from e

    async def list_files(self, path: str) -> list[tuple[str, bool]]:
        sandbox = self._require_sandbox()
        target = await self._resolve(path)
        try:
            from opensandbox.models.filesystem import DirectoryListEntry

            entries = await sandbox.files.list_directory(DirectoryListEntry(path=target, depth=1))
        except Exception as e:
            raise self._map_error(e, f"Could not list {path!r}") from e
        result: list[tuple[str, bool]] = []
        for entry in entries:
            name = posixpath.basename(entry.path.rstrip("/")) or entry.path
            if name in (".", ".."):
                continue
            entry_type = (entry.entry_type or "").lower()
            is_dir = entry_type in {"directory", "dir"}
            result.append((name, is_dir))
        return result


def _tail_bytes_text(text: str, max_bytes: int) -> tuple[str, bool]:
    """Keep the last `max_bytes` UTF-8 bytes of `text`; report whether anything was dropped."""
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text, False
    return data[-max_bytes:].decode("utf-8", errors="replace"), True


def _is_timeout_error(error: object | None) -> bool:
    """True when an OpenSandbox ExecutionError name/message indicates a timeout."""
    if error is None:
        return False
    blob = f"{getattr(error, 'name', '')} {getattr(error, 'value', '')}".lower()
    return "timeout" in blob or "timed out" in blob


def _classify_execution(
    *,
    exit_code: int | None,
    error: object | None,
    deadline: int | None,
) -> tuple[int, bool, str | None]:
    """Map OpenSandbox execution fields to `(returncode, timed_out, error_note)`.

    `timed_out` is set only when a deadline was requested and the backend signals a
    timeout (exit -1/137, or an error whose name/message mentions timeout). A missing
    exit code or a generic `execution.error` is a normal failure — otherwise the model
    would see `[timed out after Ns]` and lengthen the timeout instead of fixing the
    real error.
    """
    error_note: str | None = None
    if error is not None:
        name = getattr(error, "name", "") or ""
        value = getattr(error, "value", "") or ""
        error_note = f"{name}: {value}".strip(": ") if name or value else str(error)

    timed_out = deadline is not None and (
        exit_code in (-1, 137) or _is_timeout_error(error)
    )
    returncode = 1 if exit_code is None or exit_code < 0 else exit_code
    return returncode, timed_out, error_note
