"""Unit tests for MCP server specs in `_spec`."""

import pytest
from pydantic import ValidationError

from harness.mcp import McpServerSpec, check_mcp_servers


def test_mcp_server_spec_stdio_parsed():
    server = McpServerSpec.model_validate(
        {
            "name": "gitlab",
            "command": "npx",
            "args": ["mcp-gitlab"],
            "env": {"GITLAB_API_URL": "${GITLAB_API_URL}"},
            "cwd": "/tmp",
        }
    )
    assert server.name == "gitlab"
    assert server.command == "npx"
    assert server.args == ["mcp-gitlab"]
    assert server.env == {"GITLAB_API_URL": "${GITLAB_API_URL}"}
    assert server.cwd == "/tmp"
    assert server.url is None


def test_mcp_server_spec_url_parsed():
    server = McpServerSpec.model_validate(
        {
            "name": "remote",
            "url": "https://example.com/mcp",
            "headers": {"Authorization": "Bearer ${TOKEN}"},
        }
    )
    assert server.url == "https://example.com/mcp"
    assert server.headers == {"Authorization": "Bearer ${TOKEN}"}
    assert server.command is None


def test_mcp_server_spec_requires_name():
    with pytest.raises(ValidationError):
        McpServerSpec.model_validate({"command": "npx"})


def test_mcp_server_spec_requires_command_or_url():
    with pytest.raises(ValidationError, match="command|url"):
        McpServerSpec.model_validate({"name": "broken"})


def test_mcp_server_spec_ignores_unknown_keys():
    server = McpServerSpec.model_validate(
        {
            "name": "gitlab",
            "command": "npx",
            "disabled": True,
            "type": "stdio",
        }
    )
    assert server.command == "npx"
    assert not hasattr(server, "disabled")


def test_check_mcp_servers_coerces_and_none():
    assert check_mcp_servers(None) is None
    servers = check_mcp_servers([{"name": "x", "url": "https://example.com/mcp"}])
    assert servers is not None
    assert servers[0].name == "x"
