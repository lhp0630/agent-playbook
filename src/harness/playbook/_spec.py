"""Playbook YAML / dataclass field types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.settings import ModelSettings

from harness.models import ModelEntry


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
