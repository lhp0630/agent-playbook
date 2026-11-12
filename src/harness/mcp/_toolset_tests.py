"""Unit tests for MCP toolset builders."""

import pytest
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import PrefixedToolset

from harness.mcp import (
    McpServerSpec,
    expand_env_vars,
    make_mcp_toolset,
    make_mcp_toolsets,
    mcp_server_env_ready,
    mcp_server_missing_env,
    required_env_vars,
)


def test_expand_env_vars_requires_defined_var():
    with pytest.raises(ValueError, match=r"\$\{MISSING_MCP_VAR\}"):
        expand_env_vars("${MISSING_MCP_VAR}")


def test_expand_env_vars_default_and_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MCP_OPTIONAL", raising=False)
    assert expand_env_vars("${MCP_OPTIONAL:-fallback}") == "fallback"
    monkeypatch.setenv("MCP_OPTIONAL", "set")
    assert expand_env_vars("${MCP_OPTIONAL:-fallback}") == "set"


def test_required_env_vars_ignores_defaults():
    assert required_env_vars("${A}") == {"A"}
    assert required_env_vars("${A:-x}") == set()
    assert required_env_vars({"GITLAB_API_URL": "${GITLAB_API_URL}", "X": "${Y:-}"}) == {
        "GITLAB_API_URL"
    }


def test_mcp_server_env_ready_preflight(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITLAB_API_URL", raising=False)
    monkeypatch.delenv("GITLAB_PERSONAL_ACCESS_TOKEN", raising=False)
    spec = McpServerSpec(
        name="gitlab",
        command="npx",
        args=["mcp-gitlab"],
        env={
            "GITLAB_API_URL": "${GITLAB_API_URL}",
            "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PERSONAL_ACCESS_TOKEN}",
        },
    )
    assert mcp_server_missing_env(spec) == {
        "GITLAB_API_URL",
        "GITLAB_PERSONAL_ACCESS_TOKEN",
    }
    assert not mcp_server_env_ready(spec)

    monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "glpat-x")
    assert mcp_server_missing_env(spec) == frozenset()
    assert mcp_server_env_ready(spec)


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


def test_make_mcp_toolsets_skips_when_required_env_unset(monkeypatch: pytest.MonkeyPatch):
    # Unset optional GitLab credentials must not block constructing other toolsets.
    monkeypatch.delenv("GITLAB_API_URL", raising=False)
    monkeypatch.delenv("GITLAB_PERSONAL_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("TOKEN", "secret")

    toolsets = make_mcp_toolsets(
        [
            McpServerSpec(
                name="gitlab",
                command="npx",
                args=["mcp-gitlab"],
                env={
                    "GITLAB_API_URL": "${GITLAB_API_URL}",
                    "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PERSONAL_ACCESS_TOKEN}",
                },
            ),
            McpServerSpec(
                name="remote",
                url="https://example.com/mcp",
                headers={"Authorization": "Bearer ${TOKEN}"},
            ),
        ]
    )
    assert len(toolsets) == 1
    assert isinstance(toolsets[0], PrefixedToolset)
    assert toolsets[0].prefix == "remote"


def test_make_mcp_toolsets_builds_when_required_env_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "glpat-x")
    toolsets = make_mcp_toolsets(
        [
            McpServerSpec(
                name="gitlab",
                command="npx",
                args=["mcp-gitlab"],
                env={
                    "GITLAB_API_URL": "${GITLAB_API_URL}",
                    "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PERSONAL_ACCESS_TOKEN}",
                },
            )
        ]
    )
    assert len(toolsets) == 1
    assert toolsets[0].prefix == "gitlab"
