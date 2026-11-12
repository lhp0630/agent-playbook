"""Build prefixed MCP toolsets from [`McpServerSpec`][harness.mcp.McpServerSpec] entries."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from typing import Any

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import AbstractToolset

from harness.mcp._spec import McpServerSpec

# Same expansion grammar as pydantic_ai.mcp.load_mcp_toolsets (`${VAR}` / `${VAR:-default}`).
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(:-([^}]*))?\}")


def expand_env_vars(value: Any) -> Any:
    """Expand `${VAR}` / `${VAR:-default}` in strings, recursively through dict/list."""
    if isinstance(value, str):

        def replace_match(match: re.Match[str]) -> str:
            var_name = match.group(1)
            has_default = match.group(2) is not None
            default_value = match.group(3) if has_default else None
            if var_name in os.environ:
                return os.environ[var_name]
            if has_default:
                return default_value or ""
            raise ValueError(f"Environment variable ${{{var_name}}} is not defined")

        return _ENV_VAR_PATTERN.sub(replace_match, value)
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


def required_env_vars(value: Any) -> set[str]:
    """Collect `${VAR}` names that have no `:-default` (must be set before expand)."""
    if isinstance(value, str):
        return {
            match.group(1) for match in _ENV_VAR_PATTERN.finditer(value) if match.group(2) is None
        }
    if isinstance(value, dict):
        names: set[str] = set()
        for item in value.values():
            names |= required_env_vars(item)
        return names
    if isinstance(value, list):
        names = set()
        for item in value:
            names |= required_env_vars(item)
        return names
    return set()


def mcp_server_missing_env(mcp_spec: McpServerSpec) -> frozenset[str]:
    """Required env names referenced by this server that are not set in the process."""
    payload = {
        "command": mcp_spec.command,
        "args": mcp_spec.args,
        "env": mcp_spec.env,
        "cwd": mcp_spec.cwd,
        "url": mcp_spec.url,
        "headers": mcp_spec.headers,
    }
    return frozenset(name for name in required_env_vars(payload) if name not in os.environ)


def mcp_server_env_ready(mcp_spec: McpServerSpec) -> bool:
    """True when every required `${VAR}` in the server config is present in the environment."""
    return not mcp_server_missing_env(mcp_spec)


def make_mcp_toolset(mcp_spec: McpServerSpec) -> AbstractToolset[Any]:
    """Build one prefixed MCP toolset the same way `load_mcp_toolsets` does per entry.

    Env expansion runs here (not at YAML load) so missing `${VAR}` only fails when the
    toolset is built. Prefer `command` when both `command` and `url` are set.
    Callers that must tolerate unset optional credentials should use
    [`make_mcp_toolsets`][harness.mcp.make_mcp_toolsets], which preflights and skips.
    """
    name = mcp_spec.name
    if mcp_spec.command is not None:
        transport = StdioTransport(
            command=expand_env_vars(mcp_spec.command),
            args=list(expand_env_vars(mcp_spec.args) or []),
            env=expand_env_vars(mcp_spec.env),
            cwd=expand_env_vars(mcp_spec.cwd),
        )
        toolset = MCPToolset(transport, id=name)
    elif mcp_spec.url is not None:
        toolset = MCPToolset(
            expand_env_vars(mcp_spec.url),
            id=name,
            headers=expand_env_vars(mcp_spec.headers),
        )
    else:
        raise ValueError(f"MCP server config {name!r} must have either `command` or `url`")
    return toolset.prefixed(name)


def make_mcp_toolsets(mcp_servers: Sequence[McpServerSpec] | None) -> list[AbstractToolset[Any]]:
    """Build prefixed toolsets for servers whose required `${VAR}`s are set.

    Servers that reference unset `${VAR}` (no `:-default`) are skipped so optional
    credentials (for example GitLab) do not block constructing the rest of the agent.
    `None` or empty returns `[]`.
    """
    if not mcp_servers:
        return []
    toolsets: list[AbstractToolset[Any]] = []
    for mcp_spec in mcp_servers:
        # Preflight before expand: missing optional MCP credentials skip this server only.
        if not mcp_server_env_ready(mcp_spec):
            continue
        toolsets.append(make_mcp_toolset(mcp_spec))
    return toolsets
