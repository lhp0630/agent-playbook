# agent-playbook

[中文](README_CN.md) | [English](README.md)

agent-playbook turns YAML agent specs into a pydantic-ai [`Capability`](https://ai.pydantic.dev/capabilities/)-based agent: named skill nodes, DynamicWorkflow orchestration, and optional MCP tools.

## Features

- **`Playbook` capability** under [`agent.harness.playbook`](agent/harness/playbook/): attach with `Agent(..., capabilities=[Playbook(...)])` or declare it in an agent-spec YAML
- Declarative agent specs under [`.agents/`](.agents/): loaded via `Agent.from_file(..., custom_capability_types=[Playbook])`
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
```

Open `http://127.0.0.1:8000` and paste a GitHub PR URL, or a GitLab MR/issue URL.

## Programmatic usage

Import from the submodule (no top-level `agent` re-export of `Playbook`):

```python
from pydantic_ai import Agent

from agent.harness.playbook import Playbook

agent = Agent.from_file(
    '.agents/code-review.yaml',
    custom_capability_types=[Playbook],
)
```

Or construct the capability in code:

```python
from pydantic_ai import Agent
from agent.harness.playbook import Playbook

agent = Agent(
    'openai:Qwen3.8-27b',
    capabilities=[
        Playbook(
            name='code-review',
            nodes=[],
            mcp_servers=[],
            models={'name': 'openai-chat:Qwen3.8-27b', 'model_provider': 'openai'},
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

## Example

| GitHub | GitLab | Result | Issues |
| --- | --- | --- | --- |
| ![Web UI — GitHub](./readme_assets/web_1.png) | ![Web UI — GitLab](./readme_assets/web_gitlab.png) | ![Web UI — result](./readme_assets/web_2.png) | ![Web UI - Issues](./readme_assets/web_issues.png) |
