"""Unit tests for MCP toolset builders."""

import pytest
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import PrefixedToolset

from harness.mcp import (
    McpServerSpec,
    expand_env_vars,
    make_mcp_toolset,
    make_mcp_toolsets,
)


def test_expand_env_vars_requires_defined_var():
    with pytest.raises(ValueError, match=r"\$\{MISSING_MCP_VAR\}"):
        expand_env_vars("${MISSING_MCP_VAR}")


def test_expand_env_vars_default_and_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MCP_OPTIONAL", raising=False)
    assert expand_env_vars("${MCP_OPTIONAL:-fallback}") == "fallback"
    monkeypatch.setenv("MCP_OPTIONAL", "set")
    assert expand_env_vars("${MCP_OPTIONAL:-fallback}") == "set"


def test_make_mcp_toolset_stdio_is_prefixed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
    toolset = make_mcp_toolset(
        McpServerSpec(
            name="gitlab",
            command="npx",
            args=["mcp-gitlab"],
            env={"GITLAB_API_URL": "${GITLAB_API_URL}"},
        )
    )
    assert isinstance(toolset, PrefixedToolset)
    assert toolset.prefix == "gitlab"
    assert isinstance(toolset.wrapped, MCPToolset)


def test_make_mcp_toolset_url_is_prefixed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TOKEN", "secret")
    toolset = make_mcp_toolset(
        McpServerSpec(
            name="remote",
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer ${TOKEN}"},
        )
    )
    assert isinstance(toolset, PrefixedToolset)
    assert toolset.prefix == "remote"
    assert isinstance(toolset.wrapped, MCPToolset)


def test_make_mcp_toolsets_empty():
    assert make_mcp_toolsets(None) == []
    assert make_mcp_toolsets([]) == []
