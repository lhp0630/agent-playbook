from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.settings import ModelSettings
from yaml import safe_load


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
    skills: list[str]
    model_config = ConfigDict(arbitrary_types_allowed=True)


class PlaybookSpec(BaseModel):
    name: str
    description: str | None = None
    instructions: str | None = None
    model_providers: list[ModelProvider]
    model_settings: ModelSettings | None = Field(default_factory=lambda: ModelSettings())
    models: list[ModelEntry] | None = None
    mcp_servers: list[McpServerSpec] | None = None
    nodes: list[PlaybookNodeSpec]
    directories: list[str] = Field(default_factory=lambda: [Path(".agents") / "skills"])
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PlaybookSpec":
        file = Path(path)
        if not file.is_file():
            raise FileNotFoundError()

        spec_dict = safe_load(file.read_bytes())
        return cls.model_validate(spec_dict)
