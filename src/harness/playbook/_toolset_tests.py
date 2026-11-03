"""Unit tests for playbook toolset helpers (skills / node agents)."""

from pathlib import Path

import pytest
from pydantic_ai.models import Model as AgentModel
from pydantic_ai.models.openai import OpenAIChatModel

from harness.playbook._spec import PlaybookNodeSpec
from harness.playbook._toolset import _scan_skills, build_node_agents

_PROVIDERS = [
    {
        "name": "default",
        "base_url": "http://llm/v1",
        "api_key": "sk-config",
    }
]


def _assert_openai_chat(model: AgentModel | None, model_id: str, base_url: str):
    assert isinstance(model, OpenAIChatModel)
    assert model.model_id == model_id
    provider = model.provider
    assert provider is not None
    assert str(provider.base_url) == base_url


def test_scan_skills_finds_skill_in_later_root(tmp_path: Path):
    # A skill living only under the second root must still resolve; raising on the
    # empty first root was the user-visible multi-directory failure mode.
    empty = tmp_path / "empty"
    empty.mkdir()
    filled = tmp_path / "skills"
    skill = filled / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# demo\n")

    paths = _scan_skills(["demo-skill"], [empty, filled])
    assert paths == [skill]


def test_scan_skills_raises_when_missing_in_all_roots(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    with pytest.raises(FileNotFoundError, match="missing-skill"):
        _scan_skills(["missing-skill"], [a, b])


def test_scan_skills_first_root_wins(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for root in (first, second):
        skill = root / "demo-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# demo\n")

    paths = _scan_skills(["demo-skill"], [first, second])
    assert paths == [first / "demo-skill"]


def test_build_node_agents_uses_playbook_models_when_node_omits():
    nodes = [PlaybookNodeSpec(name="node_a", skills=[])]
    playbook_models = [{"name": "openai-chat:ornith:35b", "model_provider": "default"}]

    agents = build_node_agents(
        nodes,
        model_providers=_PROVIDERS,
        directories=[],
        model_settings=None,
        models=playbook_models,
    )
    assert len(agents) == 1
    _assert_openai_chat(agents[0].model, "openai:ornith:35b", "http://llm/v1/")


def test_build_node_agents_node_models_override_playbook():
    nodes = [
        PlaybookNodeSpec(
            name="node_a",
            skills=[],
            models=[{"name": "openai-chat:node-model", "model_provider": "default"}],
        )
    ]
    playbook_models = [{"name": "openai-chat:ornith:35b", "model_provider": "default"}]

    agents = build_node_agents(
        nodes,
        model_providers=_PROVIDERS,
        directories=[],
        model_settings=None,
        models=playbook_models,
    )
    _assert_openai_chat(agents[0].model, "openai:node-model", "http://llm/v1/")


def test_build_node_agents_raises_without_models():
    nodes = [PlaybookNodeSpec(name="node_a", skills=[])]
    with pytest.raises(ValueError, match="No model configured"):
        build_node_agents(
            nodes,
            model_providers=_PROVIDERS,
            directories=[],
            model_settings=None,
            models=None,
        )
