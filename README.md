# agent-playbook

[中文](README_CN.md) | [English](README.md)

agent-playbook is YAML-configured multi-agent workflows powered by pydantic-ai DynamicWorkflow and Agent Skills.

## Features

- YAML playbooks under [`.agents/`](.agents/): multi-agent `DynamicWorkflow` nodes composed with Agent Skills
- Built-in `code-review`

## Installation

Python 3.10+. Uses [uv](https://docs.astral.sh/uv/) for dependencies:

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
# Optional — enable GitLab MCP for GitLab URLs
GITLAB_API_URL=https://gitlab.example.com/api/v4
GITLAB_PERSONAL_ACCESS_TOKEN=glpat-xxx
```

Run a playbook:

```bash
agent
```

Open `http://127.0.0.1:8000` and paste a GitHub PR URL, or a GitLab MR URL.

## Playbook YAML

| Field | Required | Description |
| --- | :---: | --- |
| `name` | ✓ | Unique ID, e.g. `code-review` |
| `description` | | One-line summary; used to match a playbook per session |
| `instructions` | | Orchestrator runbook |
| `model_providers` | ✓ | LLM provider list (`name`, `base_url`, `api_key`) |
| `model_providers[].name` | ✓ | Provider ID, e.g. `openai` |
| `model_providers[].base_url` | ✓ | API base URL |
| `model_providers[].api_key` | ✓ | API key |
| `models` | | Model list; if omitted, falls back to `OPENAI_*` env vars |
| `models[].name` | ✓ | Model ID, e.g. `gpt-4o-mini` |
| `models[].model_provider` | ✓ | Provider `name` from `model_providers` |
| `model_settings` | | pydantic-ai `ModelSettings` (e.g. `temperature`) |
| `mcp_servers` | | MCP tool list |
| `mcp_servers[].name` | ✓ | MCP name, e.g. `gitlab` |
| `mcp_servers[].commands` | ✓ | Command array; first element is the executable |
| `mcp_servers[].env_vars` | | Env var names, or a `key: value` map |
| `directories` | | Skill library path; default `.agents/skills` |
| `nodes` | ✓ | Workflow nodes, executed in list order |
| `nodes[].name` | ✓ | Node name; normalized for `run_workflow` |
| `nodes[].instructions` | | Node prompt |
| `nodes[].skills` | ✓ | Skill name array, scanned from `directories` |
| `nodes[].models` | | Optional per-node model override |
| `nodes[].model_settings` | | Optional per-node settings override |

## Example

| GitHub | GitLab | Result |
| --- | --- | --- |
| ![Web UI — GitHub](./readme_assets/web_1.png) | ![Web UI — GitLab](./readme_assets/web_gitlab.png) | ![Web UI — result](./readme_assets/web_2.png) |
