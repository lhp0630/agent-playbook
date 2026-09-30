"""Unit tests for `resolve_models` and related toolset helpers."""

from pathlib import Path

import pytest
from pydantic_ai.models import Model as AgentModel
from pydantic_ai.models.openai import OpenAIChatModel

from agent.harness.playbook._spec import PlaybookNodeSpec
from agent.harness.playbook._toolset import (
    _scan_skills,
    build_node_agents,
    resolve_models,
)

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


def test_resolve_models_uses_configured_provider():
    # The first model in the list is resolved against the configured provider
    # (base_url from playbook YAML, not an env var).
    models = resolve_models(
        [
            {"name": "openai-chat:Qwen3.8-27b", "model_provider": "default"},
            {"name": "openai-chat:other", "model_provider": "default"},
        ],
        _PROVIDERS,
    )
    assert len(models) == 2
    _assert_openai_chat(models[0], "openai:Qwen3.8-27b", "http://llm/v1/")
    _assert_openai_chat(models[1], "openai:other", "http://llm/v1/")


def test_resolve_models_missing_provider_infers(monkeypatch: pytest.MonkeyPatch):
    # An unknown model_provider skips the configured OpenAIProvider and falls
    # through to infer_model on the bare name (provider credentials from env).
    monkeypatch.setenv("OPENAI_API_KEY", "sk-infer")
    models = resolve_models(
        [{"name": "openai-chat:Qwen3.8-27b", "model_provider": "missing"}],
        _PROVIDERS,
    )
    assert len(models) == 1
    assert isinstance(models[0], OpenAIChatModel)
    assert models[0].model_id == "openai:Qwen3.8-27b"


def test_resolve_models_empty_falls_back_to_env(monkeypatch: pytest.MonkeyPatch):
    # With no `models` list, factory falls back to OPENAI_* env vars.
    monkeypatch.setenv("OPENAI_MODEL", "Qwen3.8-27b")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://env-llm/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

    models = resolve_models(None, _PROVIDERS)
    assert len(models) == 1
    _assert_openai_chat(models[0], "openai:Qwen3.8-27b", "http://env-llm/v1/")


def test_resolve_models_empty_without_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert resolve_models(None, _PROVIDERS) == []


def test_resolve_models_node_override():
    models = resolve_models(
        [{"name": "openai-chat:node-model", "model_provider": "default"}],
        _PROVIDERS,
    )
    _assert_openai_chat(models[0], "openai:node-model", "http://llm/v1/")


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


def test_build_node_agents_uses_playbook_models_when_node_omits(
    monkeypatch: pytest.MonkeyPatch,
):
    # Without playbook models forwarded, a model-less node would fall through to
    # OPENAI_* and fail when that env is unset.
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    nodes = [PlaybookNodeSpec(name="node_a", skills=[])]
    playbook_models = [{"name": "openai-chat:Qwen3.8-27b", "model_provider": "default"}]

    agents = build_node_agents(
        nodes,
        model_providers=_PROVIDERS,
        directories=[],
        model_settings=None,
        models=playbook_models,
    )
    assert len(agents) == 1
    _assert_openai_chat(agents[0].model, "openai:Qwen3.8-27b", "http://llm/v1/")


def test_build_node_agents_node_models_override_playbook():
    nodes = [
        PlaybookNodeSpec(
            name="node_a",
            skills=[],
            models=[{"name": "openai-chat:node-model", "model_provider": "default"}],
        )
    ]
    playbook_models = [{"name": "openai-chat:Qwen3.8-27b", "model_provider": "default"}]

    agents = build_node_agents(
        nodes,
        model_providers=_PROVIDERS,
        directories=[],
        model_settings=None,
        models=playbook_models,
    )
    _assert_openai_chat(agents[0].model, "openai:node-model", "http://llm/v1/")
