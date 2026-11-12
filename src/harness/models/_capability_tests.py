"""Unit tests for the Model capability."""

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel

from harness.models import Model


def test_get_model_returns_first_resolved_entry():
    cap = Model(
        model_providers=[{"name": "default", "base_url": "http://llm/v1", "api_key": "sk-config"}],
        models=[
            {"name": "openai-chat:ornith:35b", "model_provider": "default"},
            {"name": "openai-chat:other", "model_provider": "default"},
        ],
    )
    model = cap.get_model()
    assert isinstance(model, OpenAIChatModel)
    assert model.model_id == "openai:ornith:35b"


def test_get_model_returns_none_when_menu_empty():
    assert Model().get_model() is None


async def test_resolve_model_id_matches_entry_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-infer")
    cap = Model(models=[{"name": "openai-chat:ornith:35b"}])
    agent = Agent(TestModel(), capabilities=[cap])
    resolved = await cap.resolve_model_id(None, model_id="openai-chat:ornith:35b")  # type: ignore[arg-type]
    assert isinstance(resolved, OpenAIChatModel)
    assert resolved.model_id == "openai:ornith:35b"
    deferred = await cap.resolve_model_id(None, model_id="anthropic:claude-fable-5-1")  # type: ignore[arg-type]
    assert deferred is None
    del agent


def test_agent_bootstraps_from_model_capability():
    """An agent with no explicit model still constructs; Model.get_model supplies it.

    Overriding ``resolve_model_id`` defers ``agent.model`` until a run, so we assert
    the capability contribution instead of the lazy ``agent.model`` property.
    """
    cap = Model(
        model_providers=[{"name": "default", "base_url": "http://llm/v1", "api_key": "sk-config"}],
        models=[{"name": "openai-chat:ornith:35b", "model_provider": "default"}],
    )
    agent = Agent(capabilities=[cap])
    contributed = agent._root_capability.get_model()
    assert isinstance(contributed, OpenAIChatModel)
    assert contributed.model_id == "openai:ornith:35b"
