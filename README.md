# agent-playbook

[中文](README_CN.md) | [English](README.md)

YAML **PlaybookSpec** agents (extends pydantic-ai [`AgentSpec`](https://ai.pydantic.dev/)) with MCP, skills, and a web **Supervisor**.

## Architecture

| Layer | Role |
| --- | --- |
| `.agents/*.yaml` | One [`PlaybookSpec`](src/agent/playbook_spec.py) per file: AgentSpec fields plus top-level `mcp_servers` / `models` / `model_providers` |
| `capabilities` | Standard pydantic-ai capabilities (`WebFetch`, [`SkillsCapability`](https://github.com/pydantic/pydantic-ai-skills), optional [`Model`](src/harness/models/README.md), …) |
| [`harness.mcp`](src/harness/mcp/README.md) | Claude-shaped MCP entries → prefixed toolsets; skips a server when its required `${VAR}`s are unset |
| [`harness.models`](src/harness/models/README.md) | Multi-provider resolve helpers and optional Model capability |
| [`Supervisor`](src/agent/supervisor.py) | When several specs are loaded, the only web entry: handoff tools + per-agent conversation history |

There is no Playbook capability and no DynamicWorkflow `nodes` menu — specialists are plain agents built with `PlaybookSpec.to_agent()`.

## Features

- Multi-spec web entry via Supervisor; single-spec talks to that agent directly
- Top-level MCP and optional model menu on each PlaybookSpec
- Skills and other tools via the agent `capabilities` list
- Name-only model entries use pydantic-ai `infer_model` (e.g. `OPENAI_API_KEY`); custom endpoints use `model_providers`

## Installation

Python 3.11+. Uses [uv](https://docs.astral.sh/uv/) for dependencies (includes `pydantic-ai-skills`):

```bash
git clone --recurse-submodules https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups --extra agent
```

`--extra agent` installs the server extras (`fire`, `uvicorn`, `pyyaml`, …). Reusable helpers live in `src/harness/`; the CLI/web app is `src/agent/`.

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

Skill packages live under `.agents/skills/` (`code-review-skill`).

## Quick Start

Copy `.env.example` to `.env` and set credentials:

```bash
# Optional — native infer_model for name-only models (openai:/anthropic:/google:…)
# OPENAI_API_KEY=...
# ANTHROPIC_API_KEY=...

# Optional — GitLab MCP (skipped at agent build if unset; GitHub review still works)
GITLAB_API_URL=https://gitlab.example.com/api/v4
GITLAB_PERSONAL_ACCESS_TOKEN=glpat-xxx

# Optional — Outlook MCP for outlook-mail (absolute paths; one-time `npx -y @softeria/ms-365-mcp-server --login`)
MS365_MCP_TOKEN_CACHE_PATH=/absolute/path/.config/ms365-mcp/.token-cache.json
MS365_MCP_SELECTED_ACCOUNT_PATH=/absolute/path/.config/ms365-mcp/.selected-account.json
```

Start the server:

```bash
agent
```

Open `http://127.0.0.1:8000`. With both built-in PlaybookSpecs loaded, ask for a code review or for help with Outlook mail.

## Web chat

With more than one PlaybookSpec loaded, the web chat's only entry is the Supervisor agent. It hands the turn to one specialist or asks a clarifying question. The Supervisor capability keeps each specialist's message history per conversation, so outlook-mail history does not include code-review tool records. The Supervisor's own transcript is still stored by `to_web` and used to decide whether a new message continues the previous specialist.

With a single PlaybookSpec loaded, the web chat talks to that agent directly.

## Programmatic usage

```python
from agent import PlaybookSpec
from agent.supervisor import CUSTOM_CAPABILITY_TYPES

spec = PlaybookSpec.from_file('.agents/code-review.yaml')
agent = spec.to_agent(custom_capability_types=CUSTOM_CAPABILITY_TYPES)
```

- [`PlaybookSpec`](src/agent/playbook_spec.py) — AgentSpec + `mcp_servers` / `models` / `model_providers`
- [`Model`](src/harness/models/README.md) — optional Model capability and multi-provider helpers
- [`harness.mcp`](src/harness/mcp/README.md) — Claude-compatible MCP toolset builders (env preflight skip)

## Example

| Code Review | Outlook Mail |
| --- | --- |
| ![Code Review](readme_assets/img_gitlab.png) | ![Outlook Mail](readme_assets/img_outlook.png) |
