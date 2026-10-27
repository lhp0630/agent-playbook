"""Unit tests for OpenSandboxBackend against a fake sandbox. No live server."""

import shlex
from types import SimpleNamespace

import pytest
from pydantic_ai.workspaces import (
    SupportsCommands,
    SupportsFilesystem,
    SupportsRealpath,
    Workspace,
    WorkspaceBackend,
    WorkspaceError,
    WorkspaceOutputLimitError,
    WorkspaceRef,
    WorkspaceTimeoutError,
)

from harness.open_sandbox import OpenSandboxBackend
from harness.open_sandbox._backend import (
    _MAX_OUTPUT_BYTES,
    _REALPATH_SCRIPT,
    PROVIDER,
    _command_line,
    _result_from_execution,
)


class _Files:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.dirs: set[str] = {"/"}
        self.deleted_files: list[str] = []
        self.deleted_dirs: list[str] = []
        self.modes: list[int] = []

    async def read_bytes(self, path: str) -> bytes:
        return self.data[path]

    async def write_file(self, path: str, data: bytes, *, mode: int = 644) -> None:
        self.modes.append(mode)
        self.data[path] = data

    async def create_directories(self, entries: list[object]) -> None:
        for entry in entries:
            self.dirs.add(entry.path)  # type: ignore[attr-defined]

    async def get_file_info(self, paths: list[str]) -> dict[str, SimpleNamespace]:
        infos: dict[str, SimpleNamespace] = {}
        for path in paths:
            if path in self.dirs:
                infos[path] = SimpleNamespace(path=path, entry_type="directory", size=0)
            elif path in self.data:
                infos[path] = SimpleNamespace(
                    path=path, entry_type="file", size=len(self.data[path])
                )
        return infos

    async def list_directory(self, entry: object) -> list[SimpleNamespace]:
        path = entry.path  # type: ignore[attr-defined]
        prefix = path.rstrip("/") + "/"
        found: list[SimpleNamespace] = []
        for directory in self.dirs:
            if directory.startswith(prefix) and "/" not in directory[len(prefix) :]:
                found.append(SimpleNamespace(path=directory, entry_type="directory", size=0))
        for file_path, data in self.data.items():
            if file_path.startswith(prefix) and "/" not in file_path[len(prefix) :]:
                found.append(SimpleNamespace(path=file_path, entry_type="file", size=len(data)))
        return found

    async def delete_files(self, paths: list[str]) -> None:
        self.deleted_files.extend(paths)
        for path in paths:
            self.data.pop(path, None)

    async def delete_directories(self, paths: list[str]) -> None:
        self.deleted_dirs.extend(paths)
        for path in paths:
            self.dirs.discard(path)


class _Commands:
    def __init__(self, execution: object) -> None:
        self.execution = execution
        self.calls: list[tuple[str, object]] = []
        self.realpath_map: dict[str, str] = {}
        self.realpath_exit_code = 0
        self.realpath_stderr = ""

    async def run(self, command: str, *, opts: object = None) -> object:
        self.calls.append((command, opts))
        # Simulate in-container os.path.realpath for SupportsRealpath unit tests.
        if _REALPATH_SCRIPT in command:
            path = shlex.split(command)[-1]
            if self.realpath_exit_code != 0:
                return _ok_execution(stderr=self.realpath_stderr, exit_code=self.realpath_exit_code)
            resolved = self.realpath_map.get(path, path)
            return _ok_execution(resolved)
        return self.execution


class _Sandbox:
    def __init__(self, files: _Files, commands: _Commands, sandbox_id: str = "sbx-live") -> None:
        self.files = files
        self.commands = commands
        self.id = sandbox_id


def _ok_execution(stdout: str = "", stderr: str = "", exit_code: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        logs=SimpleNamespace(
            stdout=[SimpleNamespace(text=stdout)],
            stderr=[SimpleNamespace(text=stderr)],
        ),
        error=None,
        exit_code=exit_code,
    )


def _backend(
    files: _Files | None = None, execution: object | None = None
) -> tuple[OpenSandboxBackend, _Files, _Commands]:
    store = files or _Files()
    commands = _Commands(execution or _ok_execution("ok\n"))
    backend = OpenSandboxBackend(
        sandbox=_Sandbox(store, commands),  # type: ignore[arg-type]
        working_dir="/workspace",
        env={"A": "1"},
    )
    return backend, store, commands


def test_backend_implements_workspace_protocols():
    backend, _, _ = _backend()
    assert isinstance(backend, WorkspaceBackend)
    assert isinstance(backend, SupportsCommands)
    assert isinstance(backend, SupportsFilesystem)
    assert isinstance(backend, SupportsRealpath)


def test_injected_sandbox_records_its_ref_without_creating_another():
    backend, _, _ = _backend()
    assert backend.ref == WorkspaceRef(provider=PROVIDER, id="sbx-live")


def test_ref_and_sandbox_cannot_both_be_passed():
    with pytest.raises(ValueError, match="either"):
        OpenSandboxBackend(
            sandbox=_Sandbox(_Files(), _Commands(_ok_execution())),  # type: ignore[arg-type]
            ref=WorkspaceRef(provider=PROVIDER, id="sbx-1"),
        )


def test_command_line_quotes_argv_and_rejects_a_shell_string_mismatch():
    assert _command_line(["python", "-c", "print(1)"], shell=False) == "python -c 'print(1)'"
    assert _command_line("echo hi", shell=True) == "echo hi"
    with pytest.raises(TypeError):
        _command_line("echo hi", shell=False)


def test_result_from_execution_keeps_a_nonzero_exit():
    result = _result_from_execution(_ok_execution(stderr="nope", exit_code=2), timeout=10)
    assert result.exit_code == 2
    assert result.stderr == "nope"


def test_result_from_execution_raises_on_a_deadline_timeout():
    execution = _ok_execution(stdout="partial", exit_code=-1)
    with pytest.raises(WorkspaceTimeoutError, match="timed out") as caught:
        _result_from_execution(execution, timeout=5)
    assert caught.value.stdout == "partial"


def test_result_from_execution_generic_error_is_stderr_not_a_timeout():
    execution = SimpleNamespace(
        logs=SimpleNamespace(stdout=[], stderr=[]),
        error=SimpleNamespace(name="RuntimeError", value="boom"),
        exit_code=None,
    )
    result = _result_from_execution(execution, timeout=5)
    assert result.exit_code == 1
    assert "RuntimeError: boom" in result.stderr


def test_result_from_execution_rejects_oversized_output():
    execution = _ok_execution(stdout="x" * (_MAX_OUTPUT_BYTES + 1))
    with pytest.raises(WorkspaceOutputLimitError):
        _result_from_execution(execution, timeout=None)


async def test_files_round_trip_uses_the_files_service():
    backend, store, _ = _backend()
    await backend.write_bytes("/workspace/nested/note.txt", b"hi")
    # 644, not 0o644: execd re-parses the integer as octal digits.
    assert store.modes == [644]
    assert "/workspace/nested" in store.dirs
    assert store.data["/workspace/nested/note.txt"] == b"hi"
    assert await backend.read_bytes("/workspace/nested/note.txt") == b"hi"
    entry = await backend.stat("/workspace/nested/note.txt")
    assert entry.is_dir is False
    assert entry.size == 2
    assert await backend.exists("/workspace/missing") is False
    listed = await backend.list_dir("/workspace")
    assert any(item.name == "nested" and item.is_dir for item in listed)


async def test_remove_refuses_the_workspace_root_and_deletes_a_file():
    backend, store, _ = _backend()
    store.dirs.add("/workspace")
    with pytest.raises(ValueError, match="workspace root"):
        await backend.remove("/workspace")
    await backend.write_bytes("/workspace/note.txt", b"x")
    await backend.remove("/workspace/note.txt")
    assert store.deleted_files == ["/workspace/note.txt"]
    assert await backend.exists("/workspace/note.txt") is False


async def test_run_quotes_argv_and_layers_env():
    backend, _, commands = _backend()
    result = await backend.run(["python", "-c", "print(1)"], env={"B": "2"}, timeout=3)
    assert result.stdout == "ok\n"
    assert result.exit_code == 0
    line, opts = commands.calls[0]
    assert line == "python -c 'print(1)'"
    assert opts.working_directory == "/workspace"  # type: ignore[attr-defined]
    assert opts.envs == {"A": "1", "B": "2"}  # type: ignore[attr-defined]


async def test_read_missing_file_raises_file_not_found():
    backend, _, _ = _backend()
    with pytest.raises(FileNotFoundError):
        await backend.read_bytes("/workspace/missing.txt")


async def test_read_directory_raises_is_a_directory():
    backend, store, _ = _backend()
    store.dirs.add("/workspace/nested")
    with pytest.raises(IsADirectoryError):
        await backend.read_bytes("/workspace/nested")


async def test_realpath_keeps_the_working_dir_and_missing_names():
    backend, _, commands = _backend()
    assert await backend.realpath("/workspace") == "/workspace"
    missing = "/workspace/.missing-name"
    assert await backend.realpath(missing) == missing
    line, _ = commands.calls[0]
    assert "python3" in line
    assert _REALPATH_SCRIPT in line
    assert "base64" not in line


async def test_realpath_follows_a_symlink_map_from_the_container():
    backend, _, commands = _backend()
    commands.realpath_map["/workspace/link"] = "/workspace/target"
    assert await backend.realpath("/workspace/link") == "/workspace/target"


async def test_realpath_keeps_a_trailing_newline_in_the_resolved_path():
    """POSIX allows `\\n` in a name; do not strip it the way shell substitution would."""
    backend, _, _ = _backend()
    weird = "/workspace/ends-with-newline\n"
    assert await backend.realpath(weird) == weird


async def test_realpath_joins_a_relative_path_onto_the_working_dir():
    backend, _, _ = _backend()
    assert await backend.realpath("nested") == "/workspace/nested"


async def test_realpath_raises_when_python3_fails():
    backend, _, commands = _backend()
    commands.realpath_exit_code = 127
    commands.realpath_stderr = "python3: not found"
    with pytest.raises(WorkspaceError, match="python3"):
        await backend.realpath("/workspace")


async def test_workspace_realpath_uses_native_supports_realpath():
    """Regression: FileSystem root checks must not hit the shell sized-base64 codec."""
    backend, _, commands = _backend()
    assert await Workspace(backend).realpath("/workspace") == "/workspace"
    assert commands.calls
    assert all("base64" not in line for line, _ in commands.calls)
    assert any(_REALPATH_SCRIPT in line for line, _ in commands.calls)
