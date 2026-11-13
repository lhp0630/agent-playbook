# agent-playbook

[中文](README_CN.md) | [English](README.md)

Local general-purpose agent harness on [pydantic-ai](https://ai.pydantic.dev/):
YAML specialists (MCP + skills), one web chat entry via Supervisor.

## Run

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/).

```bash
git clone --recurse-submodules https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups --extra agent
uv run agent
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Ask for a code review or help with Outlook mail.

If you cloned without submodules: `git submodule update --init --recursive`.

| Code Review | Outlook Mail |
| --- | --- |
| ![Code Review](readme_assets/img_gitlab.png) | ![Outlook Mail](readme_assets/img_outlook.png) |

## What you get

- Local web chat for specialist work (code review, mail, …)
- Add a specialist by dropping YAML under `.agents/` (MCP, skills, models in one file)
- Several specialists share one chat; Supervisor hands off and keeps histories apart
- Optional credentials: unset MCP vars skip that server so the app still starts

## Boundaries

| Layer | Role |
| --- | --- |
| `.agents/*.yaml` | One specialist per file |
| `src/agent/` | CLI, web entry, Supervisor |
| `src/harness/` | MCP / model helpers |
| `.agents/skills/` | Skill packages |

No Playbook capability or DynamicWorkflow `nodes` — each YAML builds a plain agent. One spec → chat that agent; several → Supervisor is the only web entry.

## Configure (optional)

Copy `.env.example` to `.env` when a specialist needs credentials (models, GitLab MCP, Outlook MCP).

```yaml
# .agents/code-review.yaml (sketch)
name: code-review
capabilities:
  - WebFetch: { local: true }
  - SkillsCapability:
      directories: [.agents/skills]
      include: [code-review-skill]
```

## License

[MIT](LICENSE)
