"""Playbook capability: YAML-shaped multi-agent workflows as an Agent capability."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models import Model as AgentModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import AgentDepsT
from pydantic_ai.toolsets import AgentToolset

try:
    from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow as _  # noqa: F401
except ImportError as _import_error:  # pragma: no cover
    raise ImportError(
        "Playbook requires DynamicWorkflow. Install it with: "
        'pip install "pydantic-ai-harness[dynamic-workflow]"'
    ) from _import_error

from harness.models import Model, ModelEntry, ModelProvider, normalize_models, resolve_models
from harness.playbook._spec import McpServerSpec, PlaybookNodeSpec
from harness.playbook._toolset import PlaybookToolset

if TYPE_CHECKING:
    from pydantic_ai import AbstractAgent
    from pydantic_ai._instructions import AgentInstructions


def _find_model_capability(agent: AbstractAgent[Any, Any]) -> Model[Any] | None:
    found: Model[Any] | None = None

    def visit(cap: AbstractCapability[Any]) -> None:
        nonlocal found
        if found is None and isinstance(cap, Model):
            found = cap

    agent._root_capability.apply(visit)  # pyright: ignore[reportPrivateUsage]
    return found


@dataclass(kw_only=True)
class Playbook(AbstractCapability[AgentDepsT]):
    """Multi-agent playbook capability (nodes + MCP + optional local models).

    Builds named sub-agents from `nodes` (with optional skills) and exposes them
    through [`DynamicWorkflow`][pydantic_ai_harness.dynamic_workflow.DynamicWorkflow]
    plus any configured MCP servers, via
    [`PlaybookToolset`][harness.playbook.PlaybookToolset].

    When `models` / `model_providers` are omitted, [`for_agent`][Playbook.for_agent]
    inherits them from a sibling [`Model`][harness.models.Model] capability.

    ```python
    from pydantic_ai import Agent
    from harness.playbook import Playbook

    agent = Agent(
        'openai:ornith:35b',
        capabilities=[
            Playbook(
                name='code-review',
                nodes=[],
                mcp_servers=[],
                models={'name': 'openai-chat:ornith:35b', 'model_provider': 'openai'},
                model_providers=[
                    {
                        'name': 'openai',
                        'base_url': 'https://api.openai.com/v1',
                        'api_key': '...',
                    }
                ],
            )
        ],
    )
    ```
    """

    name: str = ""
    """Unique playbook id, e.g. `code-review`. Optional under agent-spec (agent owns `name`)."""

    nodes: Sequence[PlaybookNodeSpec] = ()
    """Workflow nodes compiled into DynamicWorkflow sub-agents."""

    mcp_servers: Sequence[McpServerSpec] | None = None
    """Optional MCP servers attached to the orchestrator toolset."""

    models: ModelEntry | Sequence[ModelEntry] | Mapping[str, str] | None = None
    """Orchestrator (and default node) model entries; a single mapping is allowed."""

    model_providers: Sequence[ModelProvider] = ()
    """Provider credentials referenced by `models[].model_provider`."""

    instructions: str | None = None
    """Orchestrator system instructions contributed via `get_instructions`."""

    model_settings: ModelSettings | None = field(default_factory=lambda: ModelSettings())
    """Default model settings; nodes may override."""

    directories: Sequence[str | Path] = field(default_factory=lambda: [Path(".agents") / "skills"])
    """Skill library roots scanned for each node's `skills` list."""

    _normalized_models: list[ModelEntry] | None = field(init=False, repr=False)
    _nodes: list[PlaybookNodeSpec] = field(init=False, repr=False)
    _mcp_servers: list[McpServerSpec] | None = field(init=False, repr=False)
    _toolset: PlaybookToolset[AgentDepsT] | None = field(init=False, default=None, repr=False)
    _effective_models: list[ModelEntry] | None = field(init=False, repr=False)
    _effective_model_providers: Sequence[ModelProvider] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_normalized_models", normalize_models(self.models))
        object.__setattr__(self, "_effective_models", self._normalized_models)
        object.__setattr__(self, "_effective_model_providers", self.model_providers)
        nodes = [
            node if isinstance(node, PlaybookNodeSpec) else PlaybookNodeSpec.model_validate(node)
            for node in self.nodes
        ]
        object.__setattr__(self, "_nodes", nodes)
        mcp_servers = None
        if self.mcp_servers is not None:
            mcp_servers = [
                s if isinstance(s, McpServerSpec) else McpServerSpec.model_validate(s)
                for s in self.mcp_servers
            ]
        object.__setattr__(self, "_mcp_servers", mcp_servers)

    @classmethod
    def from_spec(
        cls,
        *,
        name: str = "",
        description: str | None = None,
        nodes: Sequence[PlaybookNodeSpec] = (),
        mcp_servers: Sequence[McpServerSpec] | None = None,
        models: ModelEntry | Sequence[ModelEntry] | Mapping[str, str] | None = None,
        model_providers: Sequence[ModelProvider] = (),
        instructions: str | None = None,
        model_settings: ModelSettings | None = None,
        directories: Sequence[str | Path] | None = None,
        id: str | None = None,
        defer_loading: bool = False,
    ) -> Playbook[Any]:
        """Create from YAML/JSON agent-spec fields (or equivalent kwargs)."""
        kwargs: dict[str, Any] = {
            "name": name,
            "nodes": nodes,
            "mcp_servers": mcp_servers,
            "models": models,
            "model_providers": model_providers,
            "instructions": instructions,
            "description": description,
            "id": id,
            "defer_loading": defer_loading,
        }
        if model_settings is not None:
            kwargs["model_settings"] = model_settings
        if directories is not None:
            kwargs["directories"] = directories
        return cls(**kwargs)

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return "Playbook"

    def for_agent(self, agent: AbstractAgent[AgentDepsT, Any]) -> Playbook[AgentDepsT]:
        """Inherit empty models/providers from a sibling Model capability."""
        sibling = _find_model_capability(agent)
        if sibling is None:
            return self
        providers: Sequence[ModelProvider] = (
            self.model_providers if self.model_providers else sibling.model_providers
        )
        models = self._normalized_models if self._normalized_models else sibling.normalized_models
        if providers is self._effective_model_providers and models is self._effective_models:
            return self
        bound = copy(self)
        object.__setattr__(bound, "_effective_model_providers", providers)
        object.__setattr__(bound, "_effective_models", models)
        object.__setattr__(bound, "_toolset", None)
        return bound

    def resolve_models(self) -> list[AgentModel]:
        """Resolve orchestrator models against effective providers."""
        return resolve_models(self._effective_models, self._effective_model_providers)

    def get_instructions(self) -> AgentInstructions[AgentDepsT] | None:
        if not self.instructions:
            return None
        return self.instructions.strip() or None

    def get_model_settings(self) -> ModelSettings | None:
        return self.model_settings

    def get_toolset(self) -> AgentToolset[AgentDepsT] | None:
        # Deferred so YAML load / ConfigManager does not require MCP env vars up front.
        if self._toolset is None:
            object.__setattr__(
                self,
                "_toolset",
                PlaybookToolset(
                    nodes=self._nodes,
                    model_providers=self._effective_model_providers,
                    directories=self.directories,
                    model_settings=self.model_settings,
                    models=self._effective_models,
                    mcp_servers=self._mcp_servers,
                    toolset_id=self.id,
                ),
            )
        return self._toolset
