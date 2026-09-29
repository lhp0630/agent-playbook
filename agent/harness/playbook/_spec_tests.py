"""Unit tests for playbook field types in `_spec`."""

import pytest
from pydantic import ValidationError

from agent.harness.playbook._spec import McpServerSpec, PlaybookNodeSpec


def test_playbook_node_requires_name():
    with pytest.raises(ValidationError):
        PlaybookNodeSpec.model_validate({"skills": []})


def test_playbook_node_defaults_skills_and_instructions():
    node = PlaybookNodeSpec.model_validate({"name": "node_a"})
    assert node.name == "node_a"
    assert node.skills == []
    assert node.instructions == ""
    assert node.models is None


def test_playbook_node_models_parsed():
    node = PlaybookNodeSpec.model_validate(
        {
            "name": "node_a",
            "skills": [],
            "models": [
                {"name": "openai-chat:node-model", "model_provider": "default"},
            ],
        }
    )
    assert node.models is not None
    assert node.models[0]["name"] == "openai-chat:node-model"
    assert node.models[0]["model_provider"] == "default"


def test_mcp_server_spec_parsed():
    server = McpServerSpec.model_validate(
        {
            "name": "gitlab",
            "commands": ["npx", "mcp-gitlab"],
            "env_vars": ["GITLAB_API_URL"],
        }
    )
    assert server.name == "gitlab"
    assert server.commands == ["npx", "mcp-gitlab"]
    assert server.env_vars == ["GITLAB_API_URL"]


def test_mcp_server_spec_requires_name():
    with pytest.raises(ValidationError):
        McpServerSpec.model_validate({"commands": ["npx"]})
