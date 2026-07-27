# agent-playbook

[中文](README_CN.md) | [English](README.md)

agent-playbook is YAML-configured multi-agent workflows powered by pydantic-ai DynamicWorkflow.

## Features

- YAML-configured agents on [pydantic-ai](https://ai.pydantic.dev/) + [pydantic-ai-harness](https://github.com/pydantic/pydantic-ai-harness) `DynamicWorkflow`
- Specialist `roles` become sub-agents (`name`, `description`, `model` from config)
- Built-in naming, debate, requirement review, and code review agents

## Installation

Python 3.10+. Uses [uv](https://docs.astral.sh/uv/) for dependencies:

```bash
git clone https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups
```

## Quick Start

Copy `.env.example` to `.env` and set your model credentials:

```bash
OPENAI_MODEL=your-model-name
OPENAI_BASE_URL=https://your-api-endpoint/v1
OPENAI_API_KEY=sk-xxx
```

Run a built-in agent (`-n` selects by name; omit for a random pick):

```bash
agent -n "name generation"
agent -n "office debate"
agent -n "requirement review"
agent -n "code review"
```

Load custom agent configs from a directory:

```bash
agent -n "my flow" -p ./my_flows
```

## Example

The code review agent reads sample code from `code_review.yaml` and runs a multi-role analysis with fix suggestions:

```bash
agent -n "code review"
```

## Built-in Agents

Config files live in `agent/builtin_agents/`:

| File | Agent name |
|------|-----------|
| `naming.yaml` | Name Generation |
| `debate.yaml` | Office Debate |
| `requirement_review.yaml` | Requirement Review |
| `code_review.yaml` | Code Review |

Each YAML supplies the orchestrator `name` / `description` / `llm.model`, plus `roles` that become DynamicWorkflow sub-agents.

## Custom Agents

Write a YAML config with `name`, `description`, `llm`, and `roles`, then load it with `-p` and run with `-n`. Optional `stages` become suggested workflow hints for the orchestrator.

## License

[MIT](LICENSE)
