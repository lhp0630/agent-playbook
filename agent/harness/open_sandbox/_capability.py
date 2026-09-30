"""OpenSandbox capability that gives agents a container sandbox to work in."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.tools import AgentDepsT
from pydantic_ai.toolsets import AgentToolset

from agent.harness.open_sandbox._session import (
    DEFAULT_IMAGE as _DEFAULT_IMAGE,
)
from agent.harness.open_sandbox._session import (
    DEFAULT_SANDBOX_TIMEOUT as _DEFAULT_SANDBOX_TIMEOUT,
)
from agent.harness.open_sandbox._session import (
    OpenSandboxSession,
)
from agent.harness.open_sandbox._tool_output import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES
from agent.harness.open_sandbox._toolset import OpenSandboxToolset

_DEFAULT_MAX_READ_BYTES = 5 * 1024 * 1024

_OWNED_INSTRUCTIONS = (
    "You have an OpenSandbox: an isolated, ephemeral container. Use `run_command` to run "
    "shell commands in it, and `read_file` / `write_file` / `list_directory` to manage files. "
    "Commands run through `sh`, so pipes and redirection work. A command times out after "
    "{default_timeout}s unless you pass `timeout_seconds` (up to {max_timeout}s). The sandbox "
    "is reset between runs, so persist anything important outside it."
)

_ATTACHED_INSTRUCTIONS = (
    "You have an OpenSandbox: an isolated container. Use `run_command` to run shell "
    "commands in it, and `read_file` / `write_file` / `list_directory` to manage files. "
    "Commands run through `sh`, so pipes and redirection work. A command times out after "
    "{default_timeout}s unless you pass `timeout_seconds` (up to {max_timeout}s). This sandbox "
    "persists across runs, so files from earlier runs can still be present."
)


@dataclass(kw_only=True)
class OpenSandbox(AbstractCapability[AgentDepsT]):
    """Access to an isolated container powered by [OpenSandbox](https://github.com/opensandbox-group/OpenSandbox).

    Gives the agent tools to run commands and manage files inside an OpenSandbox,
    a place to execute untrusted or model-generated code without touching the host.
    By default each run gets a fresh sandbox created from `image`. When the run ends,
    the capability destroys the sandbox; `sandbox_timeout` is the server-side cleanup
    backstop. To keep one sandbox across runs, either set `sandbox_id` to attach to a
    sandbox you manage elsewhere, or pass a `session` you own (an open
    `OpenSandboxSession`) so you control its lifetime.

    Requires the `opensandbox` extra (`uv add "pydantic-ai-skills[opensandbox]"`) and a
    reachable OpenSandbox server configured via `OPEN_SANDBOX_API_KEY` /
    `OPEN_SANDBOX_DOMAIN` (same stack as
    [`OpenSandboxScriptExecutor`][pydantic_ai_skills.sandboxes.opensandbox.OpenSandboxScriptExecutor]).

    ```python
    from pydantic_ai import Agent
    from agent.harness.open_sandbox import OpenSandbox

    agent = Agent('openai:Qwen3.8-27b', capabilities=[OpenSandbox()])
    result = agent.run_sync('Write a Python script that prints the first 10 primes and run it.')
    print(result.output)
    ```
    """

    image: str = _DEFAULT_IMAGE
    """Container image for owned sandboxes, as a registry tag."""

    sandbox_id: str | None = None
    """Attach to an existing sandbox by id instead of creating one.

    Attached sandboxes are not destroyed.

    The settings that only apply when creating a sandbox (`image`, `sandbox_timeout`,
    `workdir`, `env`) cannot be combined with `sandbox_id`.
    """

    session: OpenSandboxSession | None = None
    """Use a sandbox session you own and keep open across runs, instead of a per-run one.

    Pass an already-entered `OpenSandboxSession` to reuse one sandbox across runs while
    controlling its lifetime yourself. Cannot be combined with `sandbox_id` or the
    owned-sandbox creation settings.
    """

    sandbox_timeout: int = _DEFAULT_SANDBOX_TIMEOUT
    """Maximum lifetime in seconds of an owned sandbox before the server shuts it down."""

    workdir: str | None = None
    """Working directory for commands inside an owned sandbox (container default when None)."""

    env: Mapping[str, str] | None = None
    """Environment variables to set in an owned sandbox."""

    default_command_timeout: float = 60.0
    """Default timeout in seconds for one `run_command`, used when the model omits one."""

    max_command_timeout: int | None = None
    """Hard ceiling in seconds for any single `run_command`.

    None falls back to `sandbox_timeout`.
    """

    max_output_bytes: int = DEFAULT_MAX_BYTES
    """Maximum payload retained per command stream or file read, measured in UTF-8 bytes."""

    max_output_lines: int = DEFAULT_MAX_LINES
    """Maximum payload lines retained per command stream or file read."""

    max_read_bytes: int = _DEFAULT_MAX_READ_BYTES
    """Largest file `read_file` will read whole; larger files are refused with a shell hint."""

    instructions: str | None = None
    """Instructions for the model. `None` uses a mode-aware default; `''` disables."""

    def __post_init__(self) -> None:
        self._validate_configuration()
        if self.env is not None:
            self.env = dict(self.env)

        if self.session is not None:
            conflicts = self._non_default_owned_settings()
            if self.sandbox_id is not None:
                conflicts.append("sandbox_id")
            if conflicts:
                raise ValueError(
                    f"{', '.join(conflicts)} cannot be combined with `session`, which already owns "
                    "the sandbox and its configuration." + self._command_ceiling_hint(conflicts)
                )
            return
        if self.sandbox_id is None:
            ceiling = self.max_command_timeout
            if ceiling is not None and ceiling > self.sandbox_timeout:
                raise ValueError(
                    f"max_command_timeout ({ceiling}) cannot exceed sandbox_timeout "
                    f"({self.sandbox_timeout}) for an owned sandbox: the sandbox is reaped "
                    "before such a command could finish. Raise sandbox_timeout instead."
                )
            return
        ignored = self._non_default_owned_settings()
        if ignored:
            raise ValueError(
                f"{', '.join(ignored)} only apply when creating a sandbox, "
                "but `sandbox_id` attaches to an existing one. "
                "Remove them, or drop `sandbox_id` to create a sandbox."
                + self._command_ceiling_hint(ignored)
            )

    def _validate_configuration(self) -> None:
        for name, value in (
            ("sandbox_timeout", self.sandbox_timeout),
            ("max_output_bytes", self.max_output_bytes),
            ("max_output_lines", self.max_output_lines),
            ("max_read_bytes", self.max_read_bytes),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}.")

        timeout = self.default_command_timeout
        if type(timeout) is bool or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(
                f"default_command_timeout must be a positive finite number, got {timeout!r}."
            )

        ceiling = self.max_command_timeout
        if ceiling is not None and (type(ceiling) is not int or ceiling <= 0):
            raise ValueError(
                f"max_command_timeout must be a positive integer or None, got {ceiling!r}."
            )

        if self.instructions is not None and type(self.instructions) is not str:
            raise ValueError(f"instructions must be a string or None, got {self.instructions!r}.")

    def _command_ceiling_hint(self, rejected: list[str]) -> str:
        if "sandbox_timeout" not in rejected:
            return ""
        return (
            " To raise the per-command timeout ceiling on a reused sandbox, "
            "set `max_command_timeout`."
        )

    def _non_default_owned_settings(self) -> list[str]:
        return [
            name
            for name, value, default in (
                ("image", self.image, _DEFAULT_IMAGE),
                ("sandbox_timeout", self.sandbox_timeout, _DEFAULT_SANDBOX_TIMEOUT),
                ("workdir", self.workdir, None),
                ("env", self.env, None),
            )
            if value != default
        ]

    def get_instructions(self) -> str | None:
        if self.instructions is not None:
            return self.instructions or None
        reused = self.sandbox_id is not None or self.session is not None
        template = _ATTACHED_INSTRUCTIONS if reused else _OWNED_INSTRUCTIONS
        ceiling = (
            self.max_command_timeout
            if self.max_command_timeout is not None
            else self.sandbox_timeout
        )
        default_timeout = min(max(1, math.ceil(self.default_command_timeout)), ceiling)
        return template.format(default_timeout=default_timeout, max_timeout=ceiling)

    def get_toolset(self) -> AgentToolset[AgentDepsT]:
        return OpenSandboxToolset[AgentDepsT](
            image=self.image,
            sandbox_id=self.sandbox_id,
            sandbox_timeout=self.sandbox_timeout,
            workdir=self.workdir,
            default_command_timeout=self.default_command_timeout,
            max_command_timeout=self.max_command_timeout,
            max_output_bytes=self.max_output_bytes,
            max_output_lines=self.max_output_lines,
            max_read_bytes=self.max_read_bytes,
            env=self.env,
            session=self.session,
        )
