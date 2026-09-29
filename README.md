# agent-playbook

[中文](README_CN.md) | [English](README.md)

agent-playbook turns YAML playbooks into a pydantic-ai [`Capability`](https://ai.pydantic.dev/capabilities/): named skill nodes, DynamicWorkflow orchestration, and optional MCP tools.

## Features

- **`Playbook` capability** under [`agent.harness.playbook`](agent/harness/playbook/): attach with `Agent(..., capabilities=[Playbook(...)])`
- YAML playbooks under [`.agents/`](.agents/): nodes + Agent Skills + MCP, loaded via `Playbook.from_spec(**data)`
- Built-in `code-review` (first principles → 5-whys → code review), with GitHub WebFetch and GitLab MCP

## Installation

Python 3.10+. Uses [uv](https://docs.astral.sh/uv/) for dependencies (includes `pydantic-ai-harness[dynamic-workflow]`):

```bash
git clone --recurse-submodules https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

Skill packages live under `.agents/skills/` (`first-principles-skill`, `5-whys-skill`, `code-review-skill`).

## Quick Start

Copy `.env.example` to `.env` and set credentials:

```bash
# Model fallback when playbook `models` is omitted
OPENAI_MODEL=...
OPENAI_BASE_URL=...
OPENAI_API_KEY=...

# Optional — enable GitLab MCP for GitLab URLs
GITLAB_API_URL=https://gitlab.example.com/api/v4
GITLAB_PERSONAL_ACCESS_TOKEN=glpat-xxx
```

Run a playbook:

```bash
agent
# or: agent --name=code-review
```

Open `http://127.0.0.1:8000` and paste a GitHub PR URL, or a GitLab MR/issue URL.

## Programmatic usage

Import from the submodule (no top-level `agent` re-export of `Playbook`):

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

Or construct the capability in code:

```python
from pydantic_ai import Agent
from agent.harness.playbook import Playbook

agent = Agent(
    'openai:gpt-4o-mini',
    capabilities=[
        Playbook(
            name='code-review',
            nodes=[],
            mcp_servers=[],
            models={'name': 'openai-chat:gpt-4o-mini', 'model_provider': 'openai'},
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

See [`agent/harness/playbook/README.md`](agent/harness/playbook/README.md) for capability details.

## Playbook YAML

| Field | Required | Description |
| --- | :---: | --- |
| `name` | ✓ | Unique ID, e.g. `code-review` |
| `description` | | One-line summary; used to match a playbook per session |
| `instructions` | | Orchestrator runbook (via capability `get_instructions`) |
| `model_providers` | | LLM provider list (`name`, `base_url`, `api_key`); default `[]` |
| `model_providers[].name` | ✓ | Provider ID, e.g. `openai` |
| `model_providers[].base_url` | ✓ | API base URL |
| `model_providers[].api_key` | ✓ | API key |
| `models` | | Model list (one entry or a list); if omitted, falls back to `OPENAI_*` env vars |
| `models[].name` | ✓ | Model ID, e.g. `openai-chat:gpt-4o-mini` |
| `models[].model_provider` | ✓ | Provider `name` from `model_providers` |
| `model_settings` | | pydantic-ai `ModelSettings` (e.g. `temperature`) |
| `mcp_servers` | | MCP tool list (stdio `commands`) |
| `mcp_servers[].name` | ✓ | MCP name, e.g. `gitlab` |
| `mcp_servers[].commands` | ✓ | Command array; first element is the executable |
| `mcp_servers[].env_vars` | | Env var names, or a `key: value` map |
| `directories` | | Skill library path; default `.agents/skills` |
| `nodes` | | Workflow nodes → DynamicWorkflow sub-agents; default `[]` |
| `nodes[].name` | ✓ | Node name; normalized for `run_workflow` |
| `nodes[].instructions` | | Node prompt |
| `nodes[].skills` | | Skill name array, scanned from `directories`; default `[]` |
| `nodes[].models` | | Optional per-node model override |
| `nodes[].model_settings` | | Optional per-node settings override |

## Example

| GitHub | GitLab | Result | Issues |
| --- | --- | --- | --- |
| ![Web UI — GitHub](./readme_assets/web_1.png) | ![Web UI — GitLab](./readme_assets/web_gitlab.png) | ![Web UI — result](./readme_assets/web_2.png) | ![Web UI - Issues](./readme_assets/web_issues.png) |
