from __future__ import annotations

from typing import Any

from langchain.chat_models import BaseChatModel, init_chat_model

from .models import Flow, LlmConfig

_llm_cache: dict[str, Any] = {}


def make_llm(config: LlmConfig, flow: Flow) -> BaseChatModel:
    model = config.model or flow.llm.model

    if not model:
        raise ValueError(
            "No model configured. Set OPENAI_MODEL in .env, or configure llm.model in config.yaml."
        )

    base_url = config.base_url or flow.llm.base_url
    api_key = config.api_key or flow.llm.api_key
    temperature = flow.temperature

    cache_key = f"{model}|{base_url}|{api_key}"

    if cache_key not in _llm_cache:
        kwargs: dict[str, Any] = {
            "model": model,
            "model_provider": "openai",
            "temperature": temperature,
        }
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key

        _llm_cache[cache_key] = init_chat_model(**kwargs)

    return _llm_cache[cache_key]
