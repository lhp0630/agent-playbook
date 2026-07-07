# Badger

[中文](README_CN.md) | [English](README.md)

Badger is a **declarative multi-agent divide-and-conquer agent framework**. Complex tasks are decomposed into specialist roles and sequential stages, all defined in YAML — no hard-coded orchestration graph required. Each YAML file defines one agent; swapping the config defines a new domain agent.

## Features

- YAML-configured agents built on LangChain
- Multi-agent, multi-stage collaboration (`roles` + `stages` + `steps`)
- Pluggable execution plan, step executor, and lifecycle hooks
- Built-in naming, debate, requirement review, and code review agents

## Installation

Python 3.10+. Uses [uv](https://docs.astral.sh/uv/) for dependencies:

```bash
git clone https://github.com/lhp0630/badger.git && cd badger
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
uv run badger -n "name generation"
uv run badger -n "office debate"
uv run badger -n "requirement review"
uv run badger -n "code review"
```

Load custom agent configs from a directory:

```bash
uv run badger -n "my flow" -p ./my_flows
```

## Example

The code review agent reads sample code from `code_review.yaml` and runs a multi-role analysis with fix suggestions:

```bash
uv run badger -n "code review"
```

<!-- ![Code Review](./readme_assets/code_review.gif) -->

## Built-in Agents

Config files live in `agent/builtin_agents/`:

| File | Agent name |
|------|-----------|
| `naming.yaml` | Name Generation |
| `debate.yaml` | Office Debate |
| `requirement_review.yaml` | Requirement Review |
| `code_review.yaml` | Code Review |

## Custom Agents

Write a YAML config file, load it with `-p`, and run with `-n`. See [docs/technical.md](docs/technical.md) for config structure and template variables, and [docs/architecture.md](docs/architecture.md) for architecture details.

## License

[MIT](LICENSE)
