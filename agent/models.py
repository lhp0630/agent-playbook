from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = ""
    base_url: str = ""
    api_key: str = ""


class Role(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    llm: LlmConfig = Field(default_factory=LlmConfig)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    system_prompt: str = ""
    input: str = ""


class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    steps: list[Step] = Field(default_factory=list)


class Flow(BaseModel):
    """YAML agent config: roles become DynamicWorkflow sub-agents."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None

    llm: LlmConfig = Field(default_factory=LlmConfig)
    temperature: float = 0.8
    instructions: str | None = None

    topic: str | None = None
    max_rounds: int = 1

    roles: list[Role] = Field(default_factory=list)
    stages: list[Stage] = Field(default_factory=list)

    work_dir: Path | None = None
    """Directory used to resolve relative ``file:`` topic paths."""

    def resolve_topic(self) -> str:
        if not self.topic:
            return ""

        if self.topic.startswith("file:"):
            file_path = self.topic[5:]
            if self.work_dir and not Path(file_path).is_absolute():
                file_path = self.work_dir / file_path
            return Path(file_path).read_text(encoding="utf-8").strip()

        return self.topic
