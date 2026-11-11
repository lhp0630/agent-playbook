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


def make_mcp_toolset(mcp_spec: McpServerSpec) -> AbstractToolset[Any]:
    """Build one prefixed MCP toolset the same way `load_mcp_toolsets` does per entry.

    Env expansion runs here (not at YAML load) so missing `${VAR}` only fails when the
    toolset is built. Prefer `command` when both `command` and `url` are set.
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
    """Build one prefixed toolset per server; `None` or empty returns `[]`."""
    if not mcp_servers:
        return []
    return [make_mcp_toolset(mcp_spec) for mcp_spec in mcp_servers]
