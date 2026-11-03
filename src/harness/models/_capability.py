"""Model capability: shared model_providers + models menu for an agent."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models import Model as AgentModel
from pydantic_ai.tools import AgentDepsT

from harness.models.multi_provider import (
    ModelEntry,
    ModelProvider,
    normalize_models,
    resolve_models,
)

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, ModelResolutionContext


@dataclass(kw_only=True)
class Model(AbstractCapability[AgentDepsT]):
    """Named providers and a models menu the agent (and Playbook) can resolve.

    ```python
    from pydantic_ai import Agent
    from harness.models import Model

    agent = Agent(
        capabilities=[
            Model(
                model_providers=[
                    {
                        'name': 'custom_openai',
                        'base_url': 'https://llm/v1',
                        'api_key': 'sk-z',
                    },
                    {
                        'name': 'aliyun',
                        'base_url': 'https://llm.aliyun.com/v1',
                        'api_key': 'sk-z',
                    },
                ],
                models=[
                    {'name': 'openai-chat:ornith:35b', 'model_provider': 'custom_openai'},
                    {'name': 'openai-chat:deepseek-v4-flash', 'model_provider': 'aliyun'},
                    {'name': 'anthropic:claude-fable-5-1'},
                    {'name': 'google:gemini-2'},
                ],
            )
        ],
    )
    ```

    [`get_model`][pydantic_ai.capabilities.AbstractCapability.get_model] returns the
    first resolved entry so an agent without an explicit model still bootstraps.
    [`resolve_model_id`][pydantic_ai.capabilities.AbstractCapability.resolve_model_id]
    resolves IDs that appear in `models` (or any ID through listed providers); other
    IDs return `None` so pydantic-ai falls through to `infer_model`.
    """

    model_providers: Sequence[ModelProvider] = ()
    """Provider credentials referenced by `models[].model_provider`."""

    models: ModelEntry | Sequence[ModelEntry] | Mapping[str, str] | None = None
    """Model menu; a single mapping is allowed."""

    _normalized_models: list[ModelEntry] | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_normalized_models", normalize_models(self.models))

    @classmethod
    def from_spec(
        cls,
        *,
        model_providers: Sequence[ModelProvider] = (),
        models: ModelEntry | Sequence[ModelEntry] | Mapping[str, str] | None = None,
        description: str | None = None,
        id: str | None = None,
        defer_loading: bool = False,
        name: str | None = None,
    ) -> Model[Any]:
        """Create from YAML/JSON agent-spec fields (or equivalent kwargs)."""
        return cls(
            model_providers=model_providers,
            models=models,
            description=description,
            id=id,
            defer_loading=defer_loading,
        )

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return "Model"

    @property
    def normalized_models(self) -> list[ModelEntry] | None:
        return self._normalized_models

    def resolve(self) -> list[AgentModel]:
        """Resolve the configured menu against `model_providers`."""
        return resolve_models(self._normalized_models, self.model_providers)

    def get_model(self) -> AgentModel | None:
        resolved = self.resolve()
        return resolved[0] if resolved else None

    async def resolve_model_id(
        self,
        ctx: ModelResolutionContext[AgentDepsT],
        *,
        model_id: KnownModelName | str,
    ) -> AgentModel | None:
        del ctx
        entries = self._normalized_models or []
        matched = next((entry for entry in entries if entry["name"] == model_id), None)
        if matched is not None:
            return resolve_models([matched], self.model_providers)[0]
        if self.model_providers and entries:
            # Allow resolving a listed provider's model id that is not the entry name
            # only when the id matches an entry; otherwise defer to infer_model.
            return None
        return None
