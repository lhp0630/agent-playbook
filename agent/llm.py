from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from .models import ModelConfig


def make_model(config: ModelConfig) -> Model:
    model_name = config.model
    if not model_name:
        raise ValueError(
            "No model configured. Set OPENAI_MODEL in .env, "
            "or configure model.model in the playbook YAML."
        )

    base_url = config.base_url
    api_key = config.api_key
    temperature = config.temperature
    settings = ModelSettings(temperature=temperature)

    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return OpenAIChatModel(model_name, provider=provider, settings=settings)
