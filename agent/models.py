import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ModelConfig(BaseModel):
    """LLM connection and sampling settings for a playbook or cast member."""

    model_config = ConfigDict(extra="forbid")

    model: str = ""
    """Model id (e.g. gpt-4o-mini). Empty inherits the playbook default."""

    base_url: str = ""
    """OpenAI-compatible API base URL. Empty inherits the playbook default."""

    api_key: str = ""
    """API key. Empty inherits the playbook default or env."""

    temperature: float = 0.8
    """Sampling temperature for model calls."""

    max_rounds: int = 1
    """Suggested max iterative rounds for acts such as debate."""


class Cast(BaseModel):
    """One specialist in the playbook cast; becomes a DynamicWorkflow sub-agent."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Display name; normalized to a sandbox function id."""

    description: str = ""
    """What this specialist does; shown to the orchestrator and sub-agent."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    """Optional per-cast model override; empty model id uses the playbook model."""


class Cue(BaseModel):
    """A single direction within an act; folded into cast instructions / orchestrator hints."""

    model_config = ConfigDict(extra="forbid")

    cast: str
    """Cast member name this cue belongs to."""

    instructions: str = ""
    """Prompt text for this cue (supports {role_name}, {role_description})."""


class Act(BaseModel):
    """One suggested act (stage) in the playbook; guides orchestration, not a hard graph."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Act title shown in orchestrator workflow hints."""

    description: str = ""
    """Short summary of what this act should accomplish."""

    cues: list[Cue] = Field(default_factory=list)
    """Ordered cues that flesh out this act for each cast member."""


class PlaybookSpec(BaseModel):
    """Declarative playbook: cast + acts YAML that builds an orchestrator Agent."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Playbook title; also used as the orchestrator agent name."""

    description: str | None = None
    """One-line summary of the playbook purpose."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    """Default model settings for the orchestrator and cast (unless overridden)."""

    instructions: str | None = None
    """Shared instructions injected into the orchestrator and cast agents."""

    cast: list[Cast] = Field(default_factory=list)
    """Specialists exposed to DynamicWorkflow as callable sub-agents."""

    acts: list[Act] = Field(default_factory=list)
    """Suggested workflow acts used as orchestrator hints."""

    @staticmethod
    def from_yaml(path: str | Path) -> "PlaybookSpec":
        """Load a playbook spec from a YAML file."""

        e_model = os.getenv("OPENAI_MODEL", "")
        e_base_url = os.getenv("OPENAI_BASE_URL", "")
        e_api_key = os.getenv("OPENAI_API_KEY", "")

        file = Path(path)
        kwargs = yaml.safe_load(file.read_text(encoding="utf-8"))

        model_config = kwargs.get("model") or {}
        if not isinstance(model_config, dict):
            raise ValueError(f"Invalid model config in {file}: {model_config!r}")

        model = model_config.get("model", e_model)
        if not model:
            model = "gpt-4o-mini"

        base_url = model_config.get("base_url", e_base_url)
        if not base_url:
            base_url = "https://api.openai.com/v1"

        api_key = model_config.get("api_key", e_api_key)
        if not api_key:
            raise ValueError(f"Missing API key in {file} and no OPENAI_API_KEY env var set")

        kwargs["model"] = {"model": model, "base_url": base_url, "api_key": api_key}

        for member in kwargs.get("cast", []):
            member_model = member.get("model") or {}
            member["model"] = {
                "model": member_model.get("model", model),
                "base_url": member_model.get("base_url", base_url),
                "api_key": member_model.get("api_key", api_key),
            }

        return PlaybookSpec(**kwargs)
