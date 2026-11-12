# Model

Optional capability and shared helpers for a named provider menu. Prefer top-level
`models` / `model_providers` on [`PlaybookSpec`](../../agent/playbook_spec.py) when
defining YAML agents; use this capability when the menu should live under
`capabilities` instead.

[Source](./)

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

[`get_model`][pydantic_ai.capabilities.AbstractCapability.get_model] returns the first
resolved entry so an agent without an explicit model still bootstraps. Entries that
omit `model_provider` use bare `infer_model` (native provider env vars).
