from __future__ import annotations

from typing import Any

from langchain.chat_models import init_chat_model

from .models import Flow, LlmConfig

_llm_cache: dict[str, Any] = {}


def make_llm(llm_config: LlmConfig, app_config: Flow) -> Any:
    model = llm_config.model or app_config.llm.model

    if not model:
        raise ValueError(
            "No model configured. Set OPENAI_MODEL in .env, or configure llm.model in config.yaml."
        )

    base_url = llm_config.base_url or app_config.llm.base_url
    api_key = llm_config.api_key or app_config.llm.api_key
    temperature = app_config.temperature

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
