# Playbook

> [!NOTE]
> Import this capability from its submodule -- there is no top-level `agent` re-export of `Playbook`:
>
> ```python
> from agent.harness.playbook import Playbook
> ```

Turn a YAML-shaped playbook (named nodes, skills, MCP servers, model providers) into a single
[`Agent`][pydantic_ai.Agent] capability.

[Source](./)

## The problem

Multi-agent code-review (and similar) workflows need an orchestrator plus specialist sub-agents,
skills directories, and optional MCP tools. Wiring those by hand for every Agent construction is
repetitive and drifts from the playbook YAML source of truth.

## The solution

`Playbook` is an [`AbstractCapability`][pydantic_ai.capabilities.AbstractCapability] that owns the
playbook config. It builds one sub-agent per node (with [`SkillsCapability`][pydantic_ai_skills.SkillsCapability]
when skills are listed), exposes them through
[`DynamicWorkflow`][pydantic_ai_harness.dynamic_workflow.DynamicWorkflow] (`run_workflow`), and
attaches configured MCP servers -- all via [`PlaybookToolset`](./_toolset.py).

```python
from pydantic_ai import Agent
from agent.harness.playbook import Playbook

agent = Agent(
    'anthropic:claude-sonnet-4-6',
    capabilities=[
        Playbook(
            name='code-review',
            nodes=[],
            mcp_servers=[],
            models={
                'name': 'anthropic:claude-sonnet-4-6',
                'model_provider': 'openai',
            },
            model_providers=[],
        )
    ],
)
```

Load from YAML:

```python
from pathlib import Path

from pydantic_ai import Agent
from yaml import safe_load

from agent.harness.playbook import Playbook

data = safe_load(Path('.agents/code-review.yaml').read_bytes())
playbook = Playbook.from_spec(**data)
agent = Agent(
    playbook.resolve_models()[0],
    name=playbook.name,
    description=playbook.description,
    capabilities=[playbook],
)
```

## Tools

| Source | Tool | Purpose |
|---|---|---|
| DynamicWorkflow | `run_workflow` | Orchestrate node sub-agents from a sandboxed Python script |
| MCP servers | *(server tools)* | Tools from each configured `mcp_servers` entry |

## Configuration

```python
from agent.harness.playbook import Playbook

Playbook(
    name='code-review',           # unique playbook id
    nodes=[],                     # PlaybookNodeSpec sequence
    mcp_servers=[],               # optional MCP server specs
    models=None,                  # one ModelEntry mapping, or a sequence
    model_providers=[],           # providers referenced by models
    instructions=None,            # orchestrator instructions
    model_settings=None,          # default ModelSettings
    directories=['.agents/skills'],
)
```

## Further reading

- [Pydantic AI capabilities](https://ai.pydantic.dev/capabilities/)
- [Dynamic Workflow](https://github.com/pydantic/pydantic-ai-harness/tree/main/pydantic_ai_harness/dynamic_workflow/)
- [Playbook YAML](../../../README.md#playbook-yaml)
