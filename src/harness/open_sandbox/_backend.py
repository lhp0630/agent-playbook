"""An OpenSandbox container behind Pydantic AI's workspace backend protocols.

File operations go through ``Sandbox.files``. Commands go through ``Sandbox.commands``.
Building a backend does no I/O; the first operation creates a sandbox or attaches to
the one a ref names. The backend never kills it.
"""

from __future__ import annotations

import posixpath
import shlex
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import timedelta
from math import isfinite
from typing import TYPE_CHECKING, Any

import anyio
from pydantic_ai.workspaces import (
    CommandResult,
    FileEntry,
    SupportsCommands,
    SupportsFilesystem,
    WorkspaceBackend,
    WorkspaceCommand,
    WorkspaceError,
    WorkspaceOutputLimitError,
    WorkspaceRef,
    WorkspaceTimeoutError,
    WorkspaceUnavailableError,
)

if TYPE_CHECKING:
    from opensandbox import Sandbox

PROVIDER = "opensandbox"
DEFAULT_IMAGE = "opensandbox/code-interpreter:v1.1.0"
DEFAULT_SANDBOX_TIMEOUT = 300

_MISSING_SDK = (
    "OpenSandbox requires the 'opensandbox' package. Install it with `uv add opensandbox`."
)
_AUTH_MESSAGE = (
    "OpenSandbox rejected the credentials. Set OPEN_SANDBOX_API_KEY "
    "(and OPEN_SANDBOX_DOMAIN if not using the default server)."
)
_CREATE_TIMEOUT = 120
_INTERNAL_EXEC_TIMEOUT = 10
_MAX_OUTPUT_BYTES = 10 * 1024 * 1024
_OUTPUT_PREVIEW_CHARS = 64 * 1024
# execd does ParseUint(Itoa(mode), 8): the JSON number is octal digits, so 644
# becomes 0o644. A Python octal literal 0o644 is 420 and becomes mode 0o420.
_FILE_MODE = 644

_PATH_ERRORS: tuple[tuple[str, type[OSError]], ...] = (
    ("already exists", FileExistsError),
    ("permission denied", PermissionError),
    ("not a directory", NotADirectoryError),
    ("is a directory", IsADirectoryError),
    ("no such file", FileNotFoundError),
    ("not found", FileNotFoundError),
)


def _require_opensandbox() -> Any:
    try:
        from opensandbox import Sandbox as sandbox_cls
    except ImportError as exc:
        raise ImportError(_MISSING_SDK) from exc
    return sandbox_cls


def _validate_timeout(timeout: float | None) -> None:
    if timeout is not None and (
        not isinstance(timeout, (int, float)) or not isfinite(timeout) or timeout <= 0
    ):
        raise ValueError("timeout must be a positive finite number or None")


def _check_positive_int(name: str, value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}.")


def _check_working_dir(working_dir: str | None) -> str | None:
    if working_dir is None:
        return None
    if not isinstance(working_dir, str) or not posixpath.isabs(working_dir):
        raise ValueError(f"working_dir must be an absolute path, got {working_dir!r}.")
    normalized = posixpath.normpath(working_dir)
    if working_dir not in {normalized, f"{normalized}/"}:
        raise ValueError(f"working_dir must not contain '.' or '..', got {working_dir!r}.")
    return normalized


def _check_env(env: Mapping[str, str] | None) -> dict[str, str] | None:
    if env is None:
        return None
    checked: dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("`env` keys and values must be strings.")
        checked[key] = value
    return checked


def _command_line(command: WorkspaceCommand, *, shell: bool) -> str:
    """Turn a workspace command into the shell text ``commands.run`` accepts."""
    if shell:
        if not isinstance(command, str):
            raise TypeError("shell=True requires command to be a string.")
        if command == "":
            raise ValueError("command must not be empty")
        return command
    if isinstance(command, (str, bytes)) or not isinstance(command, Sequence):
        raise TypeError("shell=False requires command to be an argv sequence, not a string.")
    argv = list(command)
    if not argv:
        raise ValueError("command must not be empty")
    if not all(isinstance(part, str) for part in argv):
        raise TypeError("command argv elements must be strings.")
    return shlex.join(argv)


def _is_timeout_error(error: object | None) -> bool:
    if error is None:
        return False
    blob = f"{getattr(error, 'name', '')} {getattr(error, 'value', '')}".lower()
    return "timeout" in blob or "timed out" in blob


def _stream_text(messages: Sequence[object]) -> str:
    return "".join(getattr(message, "text", "") for message in messages)


def _result_from_execution(execution: object, *, timeout: float | None) -> CommandResult:
    """Map an OpenSandbox ``Execution`` onto a command result or a timeout error.

    A non-zero exit is a result. ``timed out`` is reserved for a deadline the caller
    asked for; a generic execution error is written into stderr so the model sees it.
    """
    logs = getattr(execution, "logs", None)
    stdout = _stream_text(getattr(logs, "stdout", ()) or ())
    stderr = _stream_text(getattr(logs, "stderr", ()) or ())
    error = getattr(execution, "error", None)
    if error is not None:
        name = getattr(error, "name", "") or ""
        value = getattr(error, "value", "") or ""
        note = f"{name}: {value}".strip(": ") if name or value else str(error)
        stderr = f"{stderr}\n{note}" if stderr else note
    exit_code = getattr(execution, "exit_code", None)
    timed_out = timeout is not None and (exit_code in (-1, 137) or _is_timeout_error(error))
    if timed_out:
        raise WorkspaceTimeoutError(
            f"Command timed out after {timeout:g} seconds",
            stdout=stdout,
            stderr=stderr,
        )
    total = len(stdout.encode()) + len(stderr.encode())
    if total > _MAX_OUTPUT_BYTES:
        raise WorkspaceOutputLimitError(
            "OpenSandbox command output exceeded the 10 MiB limit; "
            "redirect it to a file and read part of it instead",
            limit=_MAX_OUTPUT_BYTES,
            stdout=stdout[:_OUTPUT_PREVIEW_CHARS],
            stderr=stderr[:_OUTPUT_PREVIEW_CHARS],
        )
    returncode = 1 if exit_code is None or exit_code < 0 else exit_code
    return CommandResult(exit_code=returncode, stdout=stdout, stderr=stderr)


def _file_entry(info: Any) -> FileEntry:
    path = str(info.path)
    entry_type = (info.entry_type or "").lower()
    is_dir = entry_type in {"directory", "dir"}
    size = None if is_dir else info.size
    name = posixpath.basename(path.rstrip("/")) or path
    return FileEntry(name=name, path=path, is_dir=is_dir, size=size)


def _not_found(path: str) -> FileNotFoundError:
    return FileNotFoundError(f"No such file or directory in the OpenSandbox: {path!r}")


def _path_error(error: Exception, path: str) -> OSError | None:
    message = str(error).lower()
    for marker, builtin in _PATH_ERRORS:
        if marker in message:
            return builtin(f"{error} (in the OpenSandbox: {path!r})")
    return None


def _status_code(error: BaseException) -> int | None:
    status = getattr(error, "status_code", None)
    return status if isinstance(status, int) else None


def _translate(
    error: Exception,
    context: str,
    *,
    path: str | None,
    sandbox_id: str | None,
) -> Exception:
    """Map an OpenSandbox SDK error onto the workspace protocol, or return it unchanged.

    Auth failures and a gone sandbox end the run. A missing path is ``FileNotFoundError``.
    Other 5xx and untyped SDK errors propagate so a caller can retry them.
    """
    status = _status_code(error)
    if status in (401, 403) or "unauthorized" in type(error).__name__.lower():
        return WorkspaceUnavailableError(_AUTH_MESSAGE)
    from opensandbox.exceptions import SandboxReadyTimeoutException, SandboxUnhealthyException

    if isinstance(error, SandboxUnhealthyException) or (
        sandbox_id is not None and status == 404 and path is None
    ):
        named = f" {sandbox_id!r}" if sandbox_id is not None else ""
        return WorkspaceUnavailableError(
            f"The OpenSandbox{named} is no longer running (killed, or expired at its "
            "sandbox_timeout). Pass workspace='new' to start a fresh sandbox."
        )
    if isinstance(error, SandboxReadyTimeoutException):
        return TimeoutError(f"{context}: the OpenSandbox did not become ready. {error}")
    if path is not None and (status == 404 or (path_error := _path_error(error, path)) is not None):
        if status == 404:
            return _not_found(path)
        assert path_error is not None
        return path_error
    if status is not None and 400 <= status < 500:
        return WorkspaceError(f"{context}: {error}")
    return error


class OpenSandboxBackend(WorkspaceBackend, SupportsCommands, SupportsFilesystem):
    """An OpenSandbox container as a Pydantic AI workspace backend.

    Commands and file operations run inside the container, not on the host. File
    operations use the sandbox's ``files`` service. Building one does no I/O. The
    first operation creates a sandbox or attaches to ``ref``. The backend does not
    kill the sandbox; whoever holds the ref does, via ``OpenSandbox.destroy``.

    Args:
        sandbox: A live ``opensandbox.Sandbox``. Whoever created it owns killing it.
        ref: Identity of an existing sandbox to attach to on first use.
        image: OCI image for a newly created sandbox.
        sandbox_timeout: Lifetime in seconds of a newly created sandbox.
        working_dir: Absolute directory commands start in and relative paths resolve
            against. ``None`` uses the container's own directory, discovered with
            ``pwd -P`` on first use. Created when this backend creates the sandbox.
        env: Environment variables every command gets. Nothing is read from the host.
    """

    def __init__(
        self,
        *,
        sandbox: Sandbox | None = None,
        ref: WorkspaceRef | None = None,
        image: str = DEFAULT_IMAGE,
        sandbox_timeout: int = DEFAULT_SANDBOX_TIMEOUT,
        working_dir: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if ref is not None and ref.provider != PROVIDER:
            raise ValueError(
                f"unsupported workspace provider {ref.provider!r}; expected {PROVIDER!r}"
            )
        if sandbox is not None and ref is not None:
            raise ValueError("pass either `sandbox` or `ref`, not both")
        _check_positive_int("sandbox_timeout", sandbox_timeout)
        if not isinstance(image, str) or not image:
            raise ValueError(f"image must be a non-empty string, got {image!r}.")
        self._ref = ref if sandbox is None else WorkspaceRef(provider=PROVIDER, id=sandbox.id)
        self._sandbox = sandbox
        self._image = image
        self._sandbox_timeout = sandbox_timeout
        self._working_dir = _check_working_dir(working_dir)
        self._resolved_working_dir = self._working_dir
        self._env = _check_env(env)
        self._lock = anyio.Lock()

    @property
    def ref(self) -> WorkspaceRef | None:
        """Identity of the sandbox, or ``None`` before one has been created."""
        return self._ref

    async def get_sandbox(self) -> Sandbox:
        """Return the live ``opensandbox.Sandbox``, creating or attaching on first use.

        SDK features the workspace methods do not cover (snapshots, egress) go through
        this handle. Attaching to a sandbox that is gone raises
        ``WorkspaceUnavailableError`` and does not create a replacement.
        """
        return await self._sandbox_for_operation()

    async def _sandbox_for_operation(self) -> Sandbox:
        sandbox = await self._acquire()
        if self._resolved_working_dir is None:
            async with self._lock:
                if self._resolved_working_dir is None:
                    await self._discover_working_dir(sandbox)
        return sandbox

    async def _acquire(self) -> Sandbox:
        async with self._lock:
            sandbox = self._sandbox
            if sandbox is not None:
                return sandbox
            ref = self._ref
            sandbox = await self._attach(ref.id) if ref is not None else await self._create()
            # Record the id before any setup that can fail, so a later cleanup can find it.
            self._sandbox = sandbox
            self._ref = WorkspaceRef(provider=PROVIDER, id=sandbox.id)
            if ref is None and self._working_dir is not None:
                await sandbox.files.create_directories(
                    [_write_entry(self._working_dir)],
                )
            return sandbox

    async def _create(self) -> Sandbox:
        sandbox_cls = _require_opensandbox()
        created: Sandbox | None = None
        with anyio.move_on_after(_CREATE_TIMEOUT, shield=True):
            async with self._sdk_errors(None, "Could not start OpenSandbox"):
                created = await sandbox_cls.create(
                    self._image,
                    env=self._env,
                    timeout=timedelta(seconds=self._sandbox_timeout),
                )
        if created is None:
            raise TimeoutError(
                f"OpenSandbox creation did not complete within {_CREATE_TIMEOUT}s; "
                "the OpenSandbox control plane may be unreachable."
            )
        return created

    async def _attach(self, sandbox_id: str) -> Sandbox:
        sandbox_cls = _require_opensandbox()
        context = f"Could not connect to OpenSandbox {sandbox_id!r}"
        async with self._sdk_errors(sandbox_id, context):
            return await sandbox_cls.connect(sandbox_id)

    async def _discover_working_dir(self, sandbox: Sandbox) -> None:
        from opensandbox.models.execd import RunCommandOpts

        context = "Could not determine the working directory"
        try:
            execution = await sandbox.commands.run(
                "pwd -P",
                opts=RunCommandOpts(timeout=timedelta(seconds=_INTERNAL_EXEC_TIMEOUT)),
            )
        except Exception as error:
            translated = _translate(
                error, context, path=None, sandbox_id=getattr(sandbox, "id", None)
            )
            if translated is error:
                raise
            raise translated from error
        try:
            result = _result_from_execution(execution, timeout=_INTERNAL_EXEC_TIMEOUT)
        except WorkspaceTimeoutError as error:
            raise WorkspaceTimeoutError(
                f"{context}: the OpenSandbox did not answer within {_INTERNAL_EXEC_TIMEOUT}s",
                stdout=error.stdout,
                stderr=error.stderr,
            ) from error
        printed = result.stdout.removesuffix("\n")
        if result.exit_code != 0 or not posixpath.isabs(printed):
            raise WorkspaceError(
                f"{context} of OpenSandbox {getattr(sandbox, 'id', None)}: "
                f"`pwd -P` exited {result.exit_code} and printed {result.stdout!r}."
            )
        self._resolved_working_dir = posixpath.normpath(printed)

    @asynccontextmanager
    async def _sdk_errors(self, sandbox_id: str | None, context: str, path: str | None = None):
        try:
            yield
        except Exception as error:
            translated = _translate(error, context, path=path, sandbox_id=sandbox_id)
            if translated is error:
                raise
            raise translated from error

    async def working_dir(self) -> str:
        """The absolute directory commands start in."""
        await self._sandbox_for_operation()
        assert self._resolved_working_dir is not None
        return self._resolved_working_dir

    async def run(
        self,
        command: WorkspaceCommand,
        *,
        shell: bool = False,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Run a command in the sandbox working directory.

        ``commands.run`` takes shell text, so an argv sequence is quoted first.
        The server stops the command when ``timeout`` elapses.
        """
        line = _command_line(command, shell=shell)
        _validate_timeout(timeout)
        extra = _check_env(env)
        sandbox = await self._sandbox_for_operation()
        from opensandbox.models.execd import RunCommandOpts

        merged = {**(self._env or {}), **(extra or {})} or None
        opts = RunCommandOpts(
            working_directory=self._resolved_working_dir,
            timeout=None if timeout is None else timedelta(seconds=timeout),
            envs=merged,
        )
        async with self._sdk_errors(
            getattr(sandbox, "id", None), "Command could not run in the OpenSandbox"
        ):
            execution = await sandbox.commands.run(line, opts=opts)
        return _result_from_execution(execution, timeout=timeout)

    async def read_bytes(self, path: str) -> bytes:
        sandbox = await self._sandbox_for_operation()
        info = await self._stat_info(sandbox, path)
        if _file_entry(info).is_dir:
            raise IsADirectoryError(path)
        async with self._sdk_errors(getattr(sandbox, "id", None), f"Could not read {path!r}", path):
            return await sandbox.files.read_bytes(path)

    async def write_bytes(self, path: str, data: bytes) -> None:
        sandbox = await self._sandbox_for_operation()
        parent = posixpath.dirname(path)
        async with self._sdk_errors(
            getattr(sandbox, "id", None), f"Could not write {path!r}", path
        ):
            if parent and parent != "/":
                await sandbox.files.create_directories([_write_entry(parent)])
            await sandbox.files.write_file(path, data, mode=_FILE_MODE)

    async def stat(self, path: str) -> FileEntry:
        sandbox = await self._sandbox_for_operation()
        return _file_entry(await self._stat_info(sandbox, path))

    async def _stat_info(self, sandbox: Sandbox, path: str) -> object:
        async with self._sdk_errors(getattr(sandbox, "id", None), f"Could not stat {path!r}", path):
            infos = await sandbox.files.get_file_info([path])
        info = infos.get(path)
        if info is None:
            raise _not_found(path)
        return info

    async def list_dir(self, path: str) -> Sequence[FileEntry]:
        sandbox = await self._sandbox_for_operation()
        from opensandbox.models.filesystem import DirectoryListEntry

        async with self._sdk_errors(getattr(sandbox, "id", None), f"Could not list {path!r}", path):
            entries = await sandbox.files.list_directory(DirectoryListEntry(path=path, depth=1))
        listed = posixpath.normpath(path)
        result: list[FileEntry] = []
        for entry in entries:
            item = _file_entry(entry)
            if posixpath.normpath(item.path) == listed or item.name in {".", "..", ""}:
                continue
            result.append(item)
        return result

    async def make_dir(self, path: str) -> None:
        sandbox = await self._sandbox_for_operation()
        async with self._sdk_errors(
            getattr(sandbox, "id", None), f"Could not create directory {path!r}", path
        ):
            await sandbox.files.create_directories([_write_entry(path)])

    async def remove(self, path: str) -> None:
        sandbox = await self._sandbox_for_operation()
        root = await self.working_dir()
        target = posixpath.normpath(path)
        if root == target or root.startswith(target.rstrip("/") + "/"):
            raise ValueError("cannot remove the workspace root or its ancestor")
        info = await self._stat_info(sandbox, path)
        entry = _file_entry(info)
        async with self._sdk_errors(
            getattr(sandbox, "id", None), f"Could not remove {path!r}", path
        ):
            if entry.is_dir:
                await sandbox.files.delete_directories([path])
            else:
                await sandbox.files.delete_files([path])

    async def exists(self, path: str) -> bool:
        try:
            await self.stat(path)
        except FileNotFoundError:
            return False
        return True


def _write_entry(path: str) -> Any:
    from opensandbox.models.filesystem import WriteEntry

    return WriteEntry(path=path)


async def destroy_sandbox(sandbox_id: str) -> None:
    """Kill a sandbox by id. One that is already gone returns quietly."""
    sandbox_cls = _require_opensandbox()
    try:
        sandbox = await sandbox_cls.connect(sandbox_id, skip_health_check=True)
    except Exception as error:
        if _status_code(error) == 404:
            return
        translated = _translate(
            error,
            f"Could not connect to OpenSandbox {sandbox_id!r}",
            path=None,
            sandbox_id=sandbox_id,
        )
        if translated is error:
            raise
        raise translated from error
    try:
        await sandbox.kill()
    except Exception as error:
        if _status_code(error) == 404:
            return
        translated = _translate(
            error,
            f"Could not delete OpenSandbox {sandbox_id!r}",
            path=None,
            sandbox_id=sandbox_id,
        )
        if translated is error:
            raise
        raise translated from error
    finally:
        close = getattr(sandbox, "close", None)
        if close is not None:
            await close()
