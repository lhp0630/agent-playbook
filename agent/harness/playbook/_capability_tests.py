"""Unit tests for the `Playbook` capability."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from yaml import safe_load

from agent.harness.playbook import Playbook

# Shared provider + minimal playbook skeleton: every test configures one local
# `default` provider, so it lives here once and the tests only supply extras.
_BASE = """
name: test-playbook
model_providers:
  - name: default
    base_url: http://llm/v1
    api_key: sk-config
nodes:
  - name: node_a
    skills: []
"""


def _make_playbook(extra_yaml: str = "") -> Playbook:
    return Playbook.from_spec(**safe_load(_BASE + extra_yaml))


def _load_playbook(path: Path) -> Playbook:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError()
    return Playbook.from_spec(**safe_load(file.read_bytes()))


def test_from_spec_raises_when_yaml_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        _load_playbook(tmp_path / "missing.yaml")


def test_from_spec_loads_models(tmp_path: Path):
    path = tmp_path / "playbook.yml"
    path.write_text(
        _BASE
        + "models:\n"
        + "  - name: openai-chat:Qwen3.8-27b\n"
        + "    model_provider: default\n"
    )
    playbook = _load_playbook(path)
    assert playbook.models is not None
    assert playbook.models[0]["name"] == "openai-chat:Qwen3.8-27b"
    assert playbook.models[0]["model_provider"] == "default"
    assert playbook.model_providers[0]["name"] == "default"


def test_models_optional_when_absent():
    playbook = _make_playbook()
    assert playbook.models is None


def test_from_spec_rejects_missing_name():
    with pytest.raises(TypeError):
        Playbook.from_spec(
            **{
                "model_providers": [],
                "nodes": [{"name": "n", "skills": []}],
            }
        )


def test_from_spec_rejects_incomplete_node():
    with pytest.raises(ValidationError):
        Playbook.from_spec(
            **safe_load(
                """
name: x
model_providers: []
nodes:
  - skills: []
"""
            )
        )


def test_mcp_servers_parsed():
    playbook = _make_playbook(
        """
mcp_servers:
  - name: gitlab
    commands: [npx, mcp-gitlab]
    env_vars: [GITLAB_API_URL]
"""
    )
    assert playbook.mcp_servers is not None
    assert len(playbook.mcp_servers) == 1
    server = playbook.mcp_servers[0]
    assert server["name"] == "gitlab"
    assert server["commands"] == ["npx", "mcp-gitlab"]
    assert server["env_vars"] == ["GITLAB_API_URL"]


def test_node_models_override_parsed():
    playbook = _make_playbook(
        """
nodes:
  - name: node_a
    skills: []
    models:
      - name: openai-chat:node-model
        model_provider: default
"""
    )
    node = playbook.nodes[0]
    assert node["models"] is not None
    assert node["models"][0]["name"] == "openai-chat:node-model"


def test_from_spec_empty_nodes_exposes_toolset(tmp_path: Path):
    path = tmp_path / "playbook.yml"
    path.write_text(
        """
name: demo
model_providers: []
nodes: []
"""
    )
    playbook = _load_playbook(path)
    assert playbook.name == "demo"
    assert playbook.get_toolset() is not None


def test_get_instructions_strips_and_omits_blank():
    playbook = Playbook.from_spec(name="x", instructions="  hello  \n")
    assert playbook.get_instructions() == "hello"
    blank = Playbook.from_spec(name="x", instructions="   ")
    assert blank.get_instructions() is None


def test_resolve_models_delegates_to_providers():
    playbook = _make_playbook(
        """
models:
  - name: openai-chat:Qwen3.8-27b
    model_provider: default
"""
    )
    models = playbook.resolve_models()
    assert len(models) == 1
    assert models[0].model_id == "openai:Qwen3.8-27b"


def test_load_codereview_playbook() -> None:
    path = Path(".agents") / "code-review.yaml"
    playbook = _load_playbook(path)
    assert playbook.name == "code-review"
    assert playbook.nodes
    assert playbook.mcp_servers
    assert any(server["name"] == "gitlab" for server in playbook.mcp_servers)
