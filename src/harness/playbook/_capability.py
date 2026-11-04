"""Playbook capability: YAML nodes, skills, and MCP as one agent capability."""

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
from harness.playbook._spec import McpServerSpec, PlaybookNodeSpec, check_mcp_servers, check_nodes
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
    """Turn YAML nodes, skills, and MCP servers into one capability's workflow tools.

    Builds one sub-agent per node (with skills when listed) and exposes them through
    [`DynamicWorkflow`][pydantic_ai_harness.dynamic_workflow.DynamicWorkflow] plus any
    configured MCP servers, via [`PlaybookToolset`][harness.playbook.PlaybookToolset].
    When `models` / `model_providers` are empty, [`for_agent`][Playbook.for_agent]
    inherits them from a sibling [`Model`][harness.models.Model]; a local non-empty menu
    still wins.

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
    """Playbook label such as `code-review`. Optional under agent-spec (the agent owns `name`)."""

    nodes: Sequence[PlaybookNodeSpec] = ()
    """Workflow nodes compiled into DynamicWorkflow sub-agents.

    Each may list `skills` and override models; empty means MCP-only.
    """

    mcp_servers: Sequence[McpServerSpec] | None = None
    """MCP servers attached to the orchestrator toolset. `None` or empty adds none."""

    models: ModelEntry | Sequence[ModelEntry] | Mapping[str, str] | None = None
    """Orchestrator (and default node) model menu; a single mapping is allowed.

    `None` or empty defers to a sibling [`Model`][harness.models.Model] after `for_agent`.
    """

    model_providers: Sequence[ModelProvider] = ()
    """Provider credentials keyed by `models[].model_provider`.

    Empty defers to a sibling `Model`.
    """

    instructions: str | None = None
    """Orchestrator system instructions from `get_instructions`.

    Blank or `None` contributes none.
    """

    model_settings: ModelSettings | None = field(default_factory=lambda: ModelSettings())
    """Default model settings for the orchestrator and nodes that do not override them."""

    directories: Sequence[str | Path] = field(default_factory=lambda: [Path(".agents") / "skills"])
    """Skill-library roots scanned for each node's `skills` list.

    First hit wins per skill name.
    """

    id: str | None = "playbook"
    """One-off: an agent has one playbook, so the id is fixed.

    Two `Playbook` capabilities resolve to one via
    [`combine`][pydantic_ai.capabilities.AbstractCapability.combine].
    """

    _effective_models: list[ModelEntry] | None = field(init=False, repr=False)
    _effective_model_providers: Sequence[ModelProvider] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.nodes = check_nodes(self.nodes)
        self.mcp_servers = check_mcp_servers(self.mcp_servers)
        self._effective_models = normalize_models(self.models)
        self._effective_model_providers = self.model_providers

    @classmethod
    def from_spec(
        cls,
        *,
        name: str = "",
        nodes: Sequence[PlaybookNodeSpec] = (),
        mcp_servers: Sequence[McpServerSpec] | None = None,
        models: ModelEntry | Sequence[ModelEntry] | Mapping[str, str] | None = None,
        model_providers: Sequence[ModelProvider] = (),
        instructions: str | None = None,
        model_settings: ModelSettings | None = None,
        directories: Sequence[str | Path] | None = None,
    ) -> Playbook[Any]:
        """Build from an agent spec, covering the fields a spec can express.

        Every JSON-expressible parameter is named because that signature is what core reads to
        generate the spec's JSON schema.
        """
        return cls(
            name=name,
            nodes=nodes,
            mcp_servers=mcp_servers,
            models=models,
            model_providers=model_providers,
            instructions=instructions,
            model_settings=ModelSettings() if model_settings is None else model_settings,
            directories=[Path(".agents") / "skills"] if directories is None else directories,
        )

    def for_agent(self, agent: AbstractAgent[AgentDepsT, Any]) -> Playbook[AgentDepsT]:
        """Inherit empty models/providers from a sibling Model capability."""
        sibling = _find_model_capability(agent)
        if sibling is None:
            return self
        providers: Sequence[ModelProvider] = (
            self.model_providers if self.model_providers else sibling.model_providers
        )
        local_models = normalize_models(self.models)
        models = local_models if local_models else sibling.normalized_models
        if providers is self._effective_model_providers and models is self._effective_models:
            return self
        bound = copy(self)
        bound._effective_model_providers = providers
        bound._effective_models = models
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
        """Toolset providing DynamicWorkflow `run_workflow` and configured MCP servers.

        Built per call so YAML load does not require MCP env vars up front.
        """
        return PlaybookToolset(
            nodes=self.nodes,
            model_providers=self._effective_model_providers,
            directories=self.directories,
            model_settings=self.model_settings,
            models=self._effective_models,
            mcp_servers=self.mcp_servers,
            toolset_id=self.id,
        )
