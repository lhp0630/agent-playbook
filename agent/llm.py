from __future__ import annotations

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from .models import Flow, LlmConfig


def make_model(config: LlmConfig, flow: Flow) -> Model:
    """Build a pydantic-ai OpenAI-compatible model from YAML / env config."""
    model_name = config.model or flow.llm.model
    if not model_name:
        raise ValueError(
            "No model configured. Set OPENAI_MODEL in .env, "
            "or configure llm.model in the agent YAML."
        )

    base_url = (config.base_url or flow.llm.base_url) or None
    api_key = (config.api_key or flow.llm.api_key) or None
    settings = ModelSettings(temperature=flow.temperature)

    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return OpenAIChatModel(model_name, provider=provider, settings=settings)
