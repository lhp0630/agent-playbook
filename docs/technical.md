# Technical Notes

## Agent Configuration

One YAML file defines one agent. Minimal structure:

```yaml
name: "My Agent"
description: "Short agent summary"  # optional

llm:                          # global model (fallback)
  # model: "gpt-4o-mini"
temperature: 0.8
topic: "requirement text"     # or "file:example.md"
instructions: |               # optional global prompt
  IMPORTANT: Always respond in Chinese.

roles:
  - name: "Zhang Wei"
    description: "Architect, rigorous thinker."

stages:
  - name: "Stage 1"
    description: "Stage summary"  # optional
    steps:
      - role: "Zhang Wei"
        system_prompt: |
          You are {role_name}. {role_description}
        input: |
          {user_input}
          {context}
```

Per-role LLM config: set in `roles[].llm`; overrides global `llm`. Environment variables (`.env`) are the fallback; YAML values take precedence.

### Template Variables

| Variable | Meaning |
|----------|---------|
| `{user_input}` | Resolved topic content |
| `{context}` | Summary of prior step outputs |
| `{role_name}` | Current step's role name |
| `{role_description}` | Current step's role description |

### Topic Modes

- Empty — generated dynamically by agent steps (e.g. debate)
- Hardcoded — `topic: "requirement text"`
- External file — `topic: "file:example.md"` (path relative to config file directory)

### Built-in Agents

Config files live in `agent/builtin_agents/`:

| File | Agent name |
|------|-----------|
| `naming.yaml` | Name Generation |
| `debate.yaml` | Office Debate |
| `requirement_review.yaml` | Requirement Review |
| `code_review.yaml` | Code Review |

## Agent Runtime API

`FlowEngine` is the internal orchestration runtime for YAML-defined agents.

```python
from agent.engine_v2 import FlowEngine, LlmStepExecutor, RepeatingStageExecutionPlan

runtime = FlowEngine(
    agent_config,
    execution_plan=RepeatingStageExecutionPlan(),  # optional
)

async for step in runtime.astream({"user_input": "..."}):
    print(step.role, step.output)
```

### Custom StepExecutor

Implement `async def execute(self, request: StepRequest) -> StepOutput` to replace LLM calls with mocks, tools, or remote agents.

### Hooks

```python
from agent.engine_v2 import EngineHooks

hooks = EngineHooks(
    on_step_start=lambda req, _: print(f"starting {req.step.role}"),
    on_step_end=lambda req, out: print(f"done: {out.output}"),
)
```

## CLI

```bash
# Run a built-in agent
uv run badger -n "code review"

# Load a custom config directory
uv run badger -n "my agent" -p ./my_flows
```

Environment variables (`.env`):

```bash
OPENAI_MODEL=your-model-name
OPENAI_BASE_URL=https://your-api-endpoint/v1
OPENAI_API_KEY=sk-xxx
```

## Testing

```bash
uv run pytest
uv run ruff format . && uv run ruff check .
```
