"""MCP server specs aligned with `load_mcp_toolsets` `mcpServers` entries."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class McpServerSpec(BaseModel):
    """One MCP server entry in the same shape as `load_mcp_toolsets` `mcpServers` values.

    When servers are a list (not a name→config map), `name` is a field (official JSON
    uses the object key). Transport fields match Claude Desktop / Claude Code / Cursor:
    `command`/`args`/`env`/`cwd` for stdio, or `url`/`headers` for HTTP. Unknown keys
    are ignored (never honoured), matching the official loader.
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    """Server id used as the toolset id and PrefixedToolset prefix."""

    command: str | None = None
    """Executable for a stdio server; required unless `url` is set."""

    args: list[str] | None = None
    """Arguments passed to `command`. `None` or omitted means no args."""

    env: dict[str, str] | None = None
    """Environment for the stdio process. Values may use `${VAR}` / `${VAR:-default}`."""

    cwd: str | None = None
    """Working directory for the stdio process. `None` uses the parent process cwd."""

    url: str | None = None
    """HTTP or SSE endpoint when not using stdio.

    `/sse` suffix selects SSE; other URLs use streamable HTTP.
    """

    headers: dict[str, str] | None = None
    """HTTP headers for `url` servers. Values may use `${VAR}` / `${VAR:-default}`."""

    @model_validator(mode="after")
    def _require_command_or_url(self) -> Self:
        if self.command is None and self.url is None:
            raise ValueError("MCP server must have either `command` or `url`")
        return self


def check_mcp_servers(mcp_servers: Sequence[object] | None) -> list[McpServerSpec] | None:
    """Validate MCP server entries at construction; coerce mappings into specs."""
    if mcp_servers is None:
        return None
    return [
        server if isinstance(server, McpServerSpec) else McpServerSpec.model_validate(server)
        for server in mcp_servers
    ]
