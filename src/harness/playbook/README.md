# Playbook

Turn YAML nodes, skills, and MCP servers into one
[`Agent`][pydantic_ai.Agent] capability: each node becomes a sub-agent, exposed through
[`DynamicWorkflow`][pydantic_ai_harness.dynamic_workflow.DynamicWorkflow] (`run_workflow`)
plus any configured MCP tools.

[Source](./)

```python
from pydantic_ai import Agent

from harness.models import Model
from harness.playbook import Playbook

agent = Agent.from_file(
    '.agents/code-review.yaml',
    custom_capability_types=[Playbook, Model],
)
```

Or construct it in Python. When `models` / `model_providers` are empty,
[`for_agent`][harness.playbook.Playbook.for_agent] inherits them from a sibling
[`Model`][harness.models.Model] capability; a local non-empty menu still wins. Name-only
entries (no `model_provider`) use pydantic-ai `infer_model`.

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

See [`.agents/code-review.yaml`](../../../.agents/code-review.yaml) for an agent-spec
shape, and [Dynamic Workflow](https://pydantic.dev/docs/ai/harness/dynamic-workflow/)
for `run_workflow`.
