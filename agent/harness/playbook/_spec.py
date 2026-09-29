"""Playbook YAML / dataclass field types."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.settings import ModelSettings


class ModelProvider(TypedDict):
    name: str
    base_url: str
    api_key: str


class ModelEntry(TypedDict):
    name: str
    model_provider: str


class McpServerSpec(BaseModel):
    name: str
    url: str | None = None
    commands: list[str] | None = None
    env_vars: list[str] | dict[str, object] | None = None


class PlaybookNodeSpec(BaseModel):
    name: str
    instructions: str = ""
    model_settings: ModelSettings | None = None
    models: list[ModelEntry] | None = None
    skills: list[str] = Field(default_factory=list)
    model_config = ConfigDict(arbitrary_types_allowed=True)
