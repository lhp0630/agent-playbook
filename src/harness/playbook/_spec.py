"""Playbook node and MCP server specs, plus construction-time checks."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.settings import ModelSettings

from harness.models import ModelEntry


class McpServerSpec(BaseModel):
    name: str
    url: str | None = None
    commands: list[str] | None = None
    env_vars: list[str] | dict[str, object] | None = None


class PlaybookNodeSpec(BaseModel):
    name: str
    instructions: str = ""
    model_settings: ModelSettings | None = None
    models: list[ModelEntry] | None = None
    skills: list[str] = Field(default_factory=list)
    model_config = ConfigDict(arbitrary_types_allowed=True)


def check_nodes(nodes: Sequence[object]) -> list[PlaybookNodeSpec]:
    """Validate playbook nodes at construction; coerce YAML mappings into specs."""
    return [
        node if isinstance(node, PlaybookNodeSpec) else PlaybookNodeSpec.model_validate(node)
        for node in nodes
    ]


def check_mcp_servers(mcp_servers: Sequence[object] | None) -> list[McpServerSpec] | None:
    """Validate MCP server entries at construction; coerce YAML mappings into specs."""
    if mcp_servers is None:
        return None
    return [
        server if isinstance(server, McpServerSpec) else McpServerSpec.model_validate(server)
        for server in mcp_servers
    ]
