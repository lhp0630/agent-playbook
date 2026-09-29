"""Playbook toolset: DynamicWorkflow orchestration plus optional MCP servers."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers import infer_provider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import AgentDepsT, RunContext
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset, FunctionToolset, ToolsetTool
from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow
from pydantic_ai_skills import SkillsCapability

from agent.harness.playbook._spec import (
    McpServerSpec,
    ModelEntry,
    ModelProvider,
    PlaybookNodeSpec,
)


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "agent"

    if cleaned[0].isdigit():
        cleaned = f"a_{cleaned}"

    return cleaned.lower()


def normalize_models(
    models: ModelEntry | Sequence[ModelEntry] | Mapping[str, str] | None,
) -> list[ModelEntry] | None:
    if models is None:
        return None
    if isinstance(models, Mapping):
        return [ModelEntry(name=models["name"], model_provider=models["model_provider"])]
    return [ModelEntry(name=m["name"], model_provider=m["model_provider"]) for m in models]


def resolve_models(
    models: list[ModelEntry] | None,
    model_providers: Sequence[ModelProvider],
) -> list[Model]:
    """Resolve configured model entries against providers, with OPENAI_* fallback."""

    def make_model(model_entry: ModelEntry) -> Model:
        model_name = model_entry["name"]
        model_provider = next(
            (
                provider
                for provider in model_providers
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

    config_models = [make_model(model_entry) for model_entry in models] if models else []

    if not config_models:
        model_name = os.environ.get("OPENAI_MODEL")
        if model_name:
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            openai_provider = OpenAIProvider(
                base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY")
            )
            return [OpenAIChatModel(model_name, provider=openai_provider)]

    return config_models


def _make_mcp_toolset(mcp_spec: McpServerSpec) -> MCPToolset | None:
    env_vars = mcp_spec.env_vars
    env = {k: os.environ[k] for k in env_vars} if isinstance(env_vars, list) else env_vars

    if mcp_spec.commands:
        command = mcp_spec.commands[0]
        return MCPToolset(
            StdioTransport(command=command, args=mcp_spec.commands[1:], env=env),
        )
    # TODO: Construct a toolset for URL-based MCP servers.
    return None


def make_mcp_toolsets(mcp_servers: Sequence[McpServerSpec] | None) -> list[MCPToolset]:
    if not mcp_servers:
        return []
    toolsets: list[MCPToolset] = []
    for mcp_spec in mcp_servers:
        toolset = _make_mcp_toolset(mcp_spec)
        if toolset:
            toolsets.append(toolset)
    return toolsets


def _scan_skills(skills: list[str], directories: Sequence[Path | str]) -> list[Path]:
    """Resolve each skill against configured roots; first hit wins per skill."""
    skill_dirs: list[Path] = []
    roots = [Path(directory) for directory in directories]
    for skill_name in skills:
        matched = next(
            (root / skill_name for root in roots if (root / skill_name / "SKILL.md").exists()),
            None,
        )
        if matched is None:
            raise FileNotFoundError(f"{skill_name} is missing SKILL.md")
        skill_dirs.append(matched)
    return skill_dirs


def build_node_agents(
    nodes: Sequence[PlaybookNodeSpec],
    *,
    model_providers: Sequence[ModelProvider],
    directories: Sequence[Path | str],
    model_settings: ModelSettings | None,
    models: list[ModelEntry] | None = None,
) -> list[Agent]:
    node_agents: list[Agent] = []
    seen: set[str] = set()

    for node in nodes:
        normalized = normalize_name(node.name)
        if normalized in seen:
            raise ValueError(
                f"Duplicate sub-agent name {normalized} after normalizing {node.name}."
            )

        capabilities: list = []
        if node.skills:
            skill_dirs = _scan_skills(node.skills, directories)
            capabilities.append(SkillsCapability(directories=skill_dirs))

        # Node models win; otherwise playbook models, then OPENAI_* via resolve_models.
        node_models = resolve_models(
            node.models if node.models is not None else models, model_providers
        )
        if not node_models:
            raise ValueError(f"No model configured for playbook node {node.name!r}.")

        node_agents.append(
            Agent(
                model=node_models[0],
                name=normalized,
                instructions=node.instructions or None,
                capabilities=capabilities or None,
                model_settings=node.model_settings or model_settings,
            )
        )
        seen.add(normalized)

    return node_agents


class PlaybookToolset(FunctionToolset[AgentDepsT]):
    """Exposes DynamicWorkflow `run_workflow` plus playbook MCP toolsets.

    Built as a [`FunctionToolset`][pydantic_ai.toolsets.FunctionToolset] for harness
    shape consistency; tool dispatch is delegated to an inner
    [`CombinedToolset`][pydantic_ai.toolsets.CombinedToolset] of
    `DynamicWorkflow` + MCP.
    """

    def __init__(
        self,
        *,
        nodes: Sequence[PlaybookNodeSpec],
        model_providers: Sequence[ModelProvider],
        directories: Sequence[Path | str],
        model_settings: ModelSettings | None,
        models: list[ModelEntry] | None = None,
        mcp_servers: Sequence[McpServerSpec] | None = None,
        toolset_id: str | None = None,
    ) -> None:
        super().__init__(id=toolset_id)
        parts: list[AbstractToolset[AgentDepsT]] = []
        if nodes:
            node_agents = build_node_agents(
                nodes,
                model_providers=model_providers,
                directories=directories,
                model_settings=model_settings,
                models=models,
            )
            parts.append(DynamicWorkflow(agents=node_agents).get_toolset())
        parts.extend(make_mcp_toolsets(mcp_servers))
        # Empty playbook (no nodes, no MCP): keep this FunctionToolset as the inner
        # toolset so get_toolset() still returns a usable instance.
        self._inner: AbstractToolset[AgentDepsT] = (
            CombinedToolset(parts) if len(parts) > 1 else parts[0] if parts else self
        )

    async def for_run(self, ctx: RunContext[AgentDepsT]) -> AbstractToolset[AgentDepsT]:
        if self._inner is self:
            return await super().for_run(ctx)
        return await self._inner.for_run(ctx)

    async def for_run_step(self, ctx: RunContext[AgentDepsT]) -> AbstractToolset[AgentDepsT]:
        if self._inner is self:
            return await super().for_run_step(ctx)
        return await self._inner.for_run_step(ctx)

    async def __aenter__(self) -> PlaybookToolset[AgentDepsT]:
        if self._inner is not self:
            await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        if self._inner is self:
            return None
        return await self._inner.__aexit__(*args)

    async def get_tools(self, ctx: RunContext[AgentDepsT]) -> dict[str, ToolsetTool[AgentDepsT]]:
        if self._inner is self:
            return await super().get_tools(ctx)
        return await self._inner.get_tools(ctx)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        if self._inner is self:
            return await super().call_tool(name, tool_args, ctx, tool)
        return await self._inner.call_tool(name, tool_args, ctx, tool)
