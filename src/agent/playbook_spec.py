"""PlaybookSpec: AgentSpec plus MCP servers and a models menu."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Self

from pydantic import model_validator
from pydantic_ai import Agent
from pydantic_ai.agent.spec import AgentSpec
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import UserError
from pydantic_ai.models import Model as AgentModel
from pydantic_ai.toolsets import AbstractToolset

from agent.names import normalize_name
from harness.mcp import McpServerSpec, check_mcp_servers, make_mcp_toolsets
from harness.models import ModelEntry, ModelProvider, normalize_models, resolve_models


class PlaybookSpec(AgentSpec):
    """[`AgentSpec`][pydantic_ai.agent.spec.AgentSpec] plus MCP and multi-provider models.

    YAML/JSON may set top-level `mcp_servers`, `models`, and `model_providers` alongside
    the usual agent fields. Skills and other capabilities stay under `capabilities`
    (for example [`SkillsCapability`][pydantic_ai_skills.SkillsCapability]).
    """

    mcp_servers: list[McpServerSpec] | None = None
    """MCP servers built into toolsets when constructing the agent. `None` or empty adds none."""

    models: list[ModelEntry] | None = None
    """Model menu resolved against `model_providers`. Required when providers are set."""

    model_providers: list[ModelProvider] | None = None
    """Provider credentials keyed by `models[].model_provider`. `None` or empty means none."""

    @model_validator(mode="after")
    def _check_models_and_mcp(self) -> Self:
        object.__setattr__(self, "mcp_servers", check_mcp_servers(self.mcp_servers))
        if self.model_providers and not self.models:
            raise UserError(
                "`PlaybookSpec.model_providers` requires a non-empty `models` menu; "
                "set both, or omit providers."
            )
        return self

    def resolve_models(self) -> list[AgentModel]:
        """Resolve `models` against `model_providers`."""
        return resolve_models(normalize_models(self.models), self.model_providers)

    def make_mcp_toolsets(self) -> list[AbstractToolset[Any]]:
        """Build prefixed MCP toolsets from `mcp_servers`.

        Servers whose required `${VAR}` references are unset are skipped (see
        [`make_mcp_toolsets`][harness.mcp.make_mcp_toolsets]).
        """
        return make_mcp_toolsets(self.mcp_servers)

    def to_agent(
        self,
        *,
        custom_capability_types: Sequence[type[AbstractCapability[Any]]] = (),
        model: AgentModel | str | None = None,
        name: str | None = None,
    ) -> Agent[Any, Any]:
        """Construct an [`Agent`][pydantic_ai.Agent] from this playbook spec.

        Resolves the models menu for bootstrap when `model` is omitted, and attaches
        MCP toolsets from `mcp_servers` after env preflight (unset optional MCP
        credentials skip that server only).
        """
        resolved = self.resolve_models()
        effective_model = model if model is not None else (resolved[0] if resolved else None)
        toolsets = self.make_mcp_toolsets()
        return Agent.from_spec(
            self,
            custom_capability_types=list(custom_capability_types),
            model=effective_model,
            name=name if name is not None else (normalize_name(self.name) if self.name else None),
            toolsets=toolsets or None,
        )
