"""Invariants for multi-provider model resolution."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai.models import Model as AgentModel
from pydantic_ai.models.openai import OpenAIChatModel

from harness.models.multi_provider import normalize_models, resolve_models

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
    models = resolve_models(
        [
            {"name": "openai-chat:ornith:35b", "model_provider": "default"},
            {"name": "openai-chat:other", "model_provider": "default"},
        ],
        _PROVIDERS,
    )
    assert len(models) == 2
    _assert_openai_chat(models[0], "openai:ornith:35b", "http://llm/v1/")
    _assert_openai_chat(models[1], "openai:other", "http://llm/v1/")


def test_resolve_models_missing_provider_infers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-infer")
    models = resolve_models(
        [{"name": "openai-chat:ornith:35b", "model_provider": "missing"}],
        _PROVIDERS,
    )
    assert len(models) == 1
    assert isinstance(models[0], OpenAIChatModel)
    assert models[0].model_id == "openai:ornith:35b"


def test_resolve_models_empty_returns_empty_list():
    assert resolve_models(None, _PROVIDERS) == []
    assert resolve_models([], _PROVIDERS) == []


def test_resolve_models_omitted_provider_uses_infer_model(monkeypatch: pytest.MonkeyPatch):
    """Name-only entries (anthropic:/openai-chat:) go through bare infer_model."""
    sentinel = MagicMock(name="inferred-model")
    monkeypatch.setattr(
        "harness.models.multi_provider.infer_model",
        lambda name, provider_factory=None: (
            sentinel if provider_factory is None else MagicMock(name="custom")
        ),
    )
    models = resolve_models(
        [
            {"name": "anthropic:claude-fable-5-1"},
            {"name": "openai-chat:ornith:35b"},
            {"name": "google:gemini-2"},
        ],
        _PROVIDERS,
    )
    assert models == [sentinel, sentinel, sentinel]


def test_normalize_models_keeps_optional_provider():
    assert normalize_models([{"name": "anthropic:claude-fable-5-1"}]) == [
        {"name": "anthropic:claude-fable-5-1"}
    ]
    assert normalize_models([{"name": "openai-chat:ornith:35b", "model_provider": "default"}]) == [
        {"name": "openai-chat:ornith:35b", "model_provider": "default"}
    ]
    assert normalize_models(None) is None


def test_resolve_models_node_override():
    models = resolve_models(
        [{"name": "openai-chat:node-model", "model_provider": "default"}],
        _PROVIDERS,
    )
    _assert_openai_chat(models[0], "openai:node-model", "http://llm/v1/")
