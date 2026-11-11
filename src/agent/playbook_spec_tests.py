"""Invariants for PlaybookSpec loading and agent construction."""

from pathlib import Path

import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.test import TestModel
from pydantic_ai_skills import SkillsCapability

from agent.playbook_spec import PlaybookSpec
from agent.supervisor import CUSTOM_CAPABILITY_TYPES, load_spec_agent


def test_playbook_spec_rejects_providers_without_models():
    with pytest.raises(UserError, match="model_providers"):
        PlaybookSpec.from_dict(
            {
                "name": "x",
                "model_providers": [
                    {"name": "default", "base_url": "http://llm/v1", "api_key": "sk"},
                ],
            }
        )


def test_playbook_spec_parses_mcp_and_models():
    spec = PlaybookSpec.from_dict(
        {
            "name": "code-review",
            "mcp_servers": [
                {
                    "name": "gitlab",
                    "command": "npx",
                    "args": ["mcp-gitlab"],
                    "env": {"GITLAB_API_URL": "${GITLAB_API_URL}"},
                }
            ],
            "models": [{"name": "openai-chat:gpt-4o-mini", "model_provider": "custom_openai"}],
            "model_providers": [
                {
                    "name": "custom_openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-z",
                }
            ],
        }
    )
    assert spec.mcp_servers is not None
    assert spec.mcp_servers[0].name == "gitlab"
    assert spec.mcp_servers[0].command == "npx"
    assert len(spec.resolve_models()) == 1


def test_load_code_review_playbook_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "glpat-x")

    path = Path(".agents") / "code-review.yaml"
    spec = PlaybookSpec.from_file(path)
    assert spec.name == "code-review"
    assert spec.mcp_servers is not None
    assert any(server.name == "gitlab" for server in spec.mcp_servers)
    assert any(
        isinstance(cap.arguments, dict)
        and "code-review-skill" in (cap.arguments.get("include") or [])
        for cap in spec.capabilities
        if cap.name == "SkillsCapability"
    )

    agent = spec.to_agent(custom_capability_types=CUSTOM_CAPABILITY_TYPES, model=TestModel())
    assert agent.name == "code_review"
    root = agent._root_capability
    skills = [
        cap for cap in getattr(root, "capabilities", [root]) if isinstance(cap, SkillsCapability)
    ]
    assert skills
    assert "code-review-skill" in (skills[0].include or [])


def test_load_outlook_mail_playbook_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MS365_MCP_TOKEN_CACHE_PATH", "/tmp/ms365-mcp/.token-cache.json")
    monkeypatch.setenv(
        "MS365_MCP_SELECTED_ACCOUNT_PATH",
        "/tmp/ms365-mcp/.selected-account.json",
    )

    path = Path(".agents") / "outlook-mail.yaml"
    spec = PlaybookSpec.from_file(path)
    assert spec.instructions is not None
    assert "create-reply-draft" in spec.instructions
    assert "delete-mail-message" in spec.instructions
    assert spec.mcp_servers is not None
    server = next(item for item in spec.mcp_servers if item.name == "outlook")
    assert server.command == "npx"
    assert server.args is not None
    assert "@softeria/ms-365-mcp-server" in server.args

    agent, models = load_spec_agent(path, custom_capability_types=CUSTOM_CAPABILITY_TYPES)
    assert agent.name == "outlook_mail"
    assert models
