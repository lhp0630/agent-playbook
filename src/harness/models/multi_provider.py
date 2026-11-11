"""Resolve model entries against named providers, or via pydantic-ai `infer_model`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NotRequired, TypedDict

from pydantic_ai.models import Model, infer_model
from pydantic_ai.providers import infer_provider
from pydantic_ai.providers.openai import OpenAIProvider


class ModelProvider(TypedDict):
    name: str
    base_url: str
    api_key: str


class ModelEntry(TypedDict):
    name: str
    model_provider: NotRequired[str]


def normalize_models(models: Sequence[ModelEntry] | None) -> list[ModelEntry] | None:
    """Copy entries and drop blank `model_provider`; `None` stays `None`."""
    if models is None:
        return None
    return [_normalize_entry(entry) for entry in models]


def _normalize_entry(entry: Mapping[str, str]) -> ModelEntry:
    normalized: ModelEntry = {"name": entry["name"]}
    provider = entry.get("model_provider")
    if provider:
        normalized["model_provider"] = provider
    return normalized


def resolve_models(
    models: Sequence[ModelEntry] | None,
    model_providers: Sequence[ModelProvider] | None,
) -> list[Model]:
    """Resolve configured model entries against providers.

    Returns an empty list when ``models`` is ``None`` or empty. There is no
    environment-variable fallback. ``model_providers`` of ``None`` means none.
    """
    if not models:
        return []
    providers = model_providers or ()
    return [_make_model(entry, providers) for entry in models]


def _make_model(model_entry: ModelEntry, model_providers: Sequence[ModelProvider]) -> Model:
    model_name = model_entry["name"]
    provider_name = model_entry.get("model_provider")
    if not provider_name:
        return infer_model(model_name)

    model_provider = next(
        (provider for provider in model_providers if provider["name"] == provider_name),
        None,
    )
    if model_provider is None:
        return infer_model(model_name)

    def provider_factory(provider: str):
        if provider in ("openai", "openai-chat", "openai-responses"):
            return OpenAIProvider(
                base_url=model_provider["base_url"], api_key=model_provider["api_key"]
            )
        return infer_provider(provider)

    return infer_model(model_name, provider_factory)
