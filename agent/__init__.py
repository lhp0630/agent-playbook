import os
import re
from pathlib import Path
from typing import TypedDict

from fastmcp.client.transports import StdioTransport
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent
from pydantic_ai.capabilities import WebFetch
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers import infer_provider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow
from pydantic_ai_skills import SkillsCapability
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


# --- build model configuration -----------------------------------


def make_agent_models(
    spec: PlaybookSpec | PlaybookNodeSpec, model_providers: list[ModelProvider]
) -> list[Model]:

    config_providers = model_providers

    def make_model(model_entry: ModelEntry):
        model_name = model_entry["name"]
        model_provider = next(
            (
                provider
                for provider in config_providers
                if provider["name"] == model_entry["model_provider"]
            ),
            None,
        )

        if not model_provider:
            return infer_model(model_name)

        def provider_factory(provider: str):
            if provider in ("openai", "openai-chat", "openai-responses"):
                return OpenAIProvider(
                    base_url=model_provider["base_url"], api_key=model_provider["api_key"]
                )

            return infer_provider(provider)

        return infer_model(model_name, provider_factory)

    config_models = [make_model(model_entry) for model_entry in spec.models] if spec.models else []

    if not config_models:
        model_name = os.environ.get("OPENAI_MODEL")
        if model_name:
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            openai_provider = OpenAIProvider(
                base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY")
            )
            return [OpenAIChatModel(model_name, provider=openai_provider)]

    return config_models


# --- build mcp tools ---------------------------------------------


def _make_mcp_toolset(mcp_spec: McpServerSpec) -> MCPToolset | None:
    env_vars = mcp_spec.env_vars
    env = {k: os.environ[k] for k in env_vars} if isinstance(env_vars, list) else env_vars

    if mcp_spec.commands:
        command = mcp_spec.commands[0]

        return MCPToolset(
            StdioTransport(command=command, args=mcp_spec.commands[1:], env=env),
        )


def _make_mcp_tools(pb_spec: PlaybookSpec) -> list[MCPToolset]:
    mcp_toolsets: list[MCPToolset] = []

    if pb_spec.mcp_servers:
        for mcp_spec in pb_spec.mcp_servers:
            mcp_toolset = _make_mcp_toolset(mcp_spec)
            if mcp_toolset:
                mcp_toolsets.append(mcp_toolset)

    return mcp_toolsets


# --- build capability --------------------------------------------


def _build_attach_capability(): ...


# --- build agent -------------------------------------------------


def _normalize_name(spec: PlaybookSpec | PlaybookNodeSpec) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", spec.name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "agent"

    if cleaned[0].isdigit():
        cleaned = f"a_{cleaned}"

    return cleaned.lower()


def _build_node_hint(node_spec: PlaybookNodeSpec) -> str:
    skills = ", ".join(node_spec.skills) if node_spec.skills else "(none)"
    prompt_prevw = (
        node_spec.instructions.strip().splitlines()[0]
        if node_spec.instructions.strip()
        else "No prompt."
    )
    if len(prompt_prevw) > 120:
        prompt_prevw = prompt_prevw[:117] + "..."
    return f"- `{_normalize_name(node_spec)}` ({node_spec.name}; skills: {skills}): {prompt_prevw}"


def _build_instructions(pb_spec: PlaybookSpec) -> str:
    prompts: list[str] = []

    if pb_spec.description:
        prompts.append(f"You orchestrate a multi-agent workflow: {pb_spec.description.strip()}")

    if pb_spec.instructions:
        prompts.append(pb_spec.instructions.strip())

    if pb_spec.nodes:
        catalog = "\n".join(_build_node_hint(node) for node in pb_spec.nodes)
        prompts.append(
            "Use the `run_workflow` tool to coordinate these nodes "
            f"(call each as an async function with `task=...`):\n{catalog}"
        )

    prompts.append(
        "Write a Python script inside `run_workflow` that calls the nodes in order, "
        "passes prior outputs into later `task` strings, and returns the final result."
    )
    return "\n\n".join(prompts)


def _scan_target_skills(skills: list[str], directories: list[Path | str]) -> list[Path]:
    skill_dirs: list[Path] = []

    for dir in directories:
        base_path = Path(dir)

        for skill_name in skills:
            skill_path = base_path / skill_name

            if not (skill_path / "SKILL.md").exists():
                raise FileNotFoundError(f"{skill_name} is missing SKILL.md")

            skill_dirs.append(skill_path)
    return skill_dirs


def make_workflow_agent(pb_spec: PlaybookSpec) -> Agent:
    node_agents: list[Agent] = []
    seen: set[str] = set()

    model_providers = pb_spec.model_providers
    model_settings = pb_spec.model_settings

    for node in pb_spec.nodes:
        normalized_name = _normalize_name(node)
        if normalized_name in seen:
            raise ValueError(
                f"Duplicate sub-agent name {normalized_name} after normalizing {node.name}."
            )

        capabilities: list = []
        if node.skills:
            skill_dirs = _scan_target_skills(node.skills, pb_spec.directories)
            capabilities.append(SkillsCapability(directories=skill_dirs))

        node_agent_models = make_agent_models(node, model_providers)

        node_agents.append(
            Agent(
                model=node_agent_models[0],
                name=normalized_name,
                instructions=node.instructions,
                capabilities=capabilities or None,
                model_settings=node.model_settings or model_settings,
            )
        )
        seen.add(normalized_name)

    agent_models = make_agent_models(pb_spec, model_providers)

    return Agent(
        model=agent_models[0],
        name=_normalize_name(pb_spec),
        description=pb_spec.description,
        instructions=_build_instructions(pb_spec),
        model_settings=model_settings,
        capabilities=[
            WebFetch(local=True),
            DynamicWorkflow(agents=node_agents),
        ],
        toolsets=_make_mcp_tools(pb_spec) or None,
    )


__version__ = "0.1.1"
__all__ = [
    "PlaybookSpec",
    "PlaybookNodeSpec",
    "McpServerSpec",
    "make_workflow_agent",
    "__version__",
]
