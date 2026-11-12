"""Model capability: named providers menu and model resolution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
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
    """Give the agent a named providers menu and resolve entries for bootstrap and model IDs.

    [`get_model`][pydantic_ai.capabilities.AbstractCapability.get_model] returns the first
    resolved entry so an agent without an explicit model still bootstraps.
    [`resolve_model_id`][pydantic_ai.capabilities.AbstractCapability.resolve_model_id]
    resolves IDs listed in `models`; others return `None` so pydantic-ai falls through to
    `infer_model`.

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
                ],
                models=[
                    {'name': 'openai-chat:ornith:35b', 'model_provider': 'custom_openai'},
                    {'name': 'anthropic:claude-fable-5-1'},
                ],
            )
        ],
    )
    ```
    """

    model_providers: Sequence[ModelProvider] | None = None
    """Provider credentials keyed by `models[].model_provider`.

    For example a custom OpenAI-compatible `base_url`. `None` or empty means none.
    """

    models: Sequence[ModelEntry] | None = None
    """Model menu. `None` or empty contributes no model.

    An entry that omits `model_provider` uses bare [`infer_model`][pydantic_ai.models.infer_model]
    (for example `anthropic:…` / `google:…`).
    """

    id: str | None = "model"
    """One-off: an agent has one model menu, so the id is fixed.

    Two `Model` capabilities resolve to one via
    [`combine`][pydantic_ai.capabilities.AbstractCapability.combine].
    """

    @classmethod
    def from_spec(
        cls,
        *,
        model_providers: Sequence[ModelProvider] | None = None,
        models: Sequence[ModelEntry] | None = None,
    ) -> Model[Any]:
        """Build from an agent spec, covering the fields a spec can express.

        Every JSON-expressible parameter is named because that signature is what core reads to
        generate the spec's JSON schema.
        """
        return cls(
            model_providers=model_providers,
            models=models,
        )

    @property
    def normalized_models(self) -> list[ModelEntry] | None:
        return normalize_models(self.models)

    def resolve(self) -> list[AgentModel]:
        """Resolve the configured menu against `model_providers`."""
        return resolve_models(self.normalized_models, self.model_providers)

    def get_model(self) -> AgentModel | None:
        # TODO(model-routing): Bootstrap should resolve only the first menu entry (later:
        # the web UI selection) so optional later providers (e.g. anthropic) are not
        # constructed up front. Longer term, treat that UI selection as the default and
        # pick other menu entries from user input via resolve_model_id / a router —
        # never eager-resolve the full menu on get_model.
        resolved = self.resolve()
        return resolved[0] if resolved else None

    async def resolve_model_id(
        self,
        ctx: ModelResolutionContext[AgentDepsT],
        *,
        model_id: KnownModelName | str,
    ) -> AgentModel | None:
        # TODO(model-routing): Entry point for per-turn / user-driven model choice from
        # the menu; keep single-entry resolution (do not build the whole menu here).
        del ctx
        entries = self.normalized_models or []
        matched = next((entry for entry in entries if entry["name"] == model_id), None)
        if matched is not None:
            return resolve_models([matched], self.model_providers)[0]
        if self.model_providers and entries:
            # Allow resolving a listed provider's model id that is not the entry name
            # only when the id matches an entry; otherwise defer to infer_model.
            return None
        return None
