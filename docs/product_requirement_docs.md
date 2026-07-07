# Product Requirements

## Vision

Badger is a **declarative multi-agent divide-and-conquer agent framework**. Complex tasks are decomposed into specialist roles and sequential stages, all defined in YAML — no hard-coded orchestration graph required. Each YAML file defines one agent; swapping the config defines a new domain agent.

Users define specialist roles and stage transitions in YAML. The orchestration runtime handles multi-agent collaboration and context passing — enabling coding agents, requirement-review agents, debate agents, and other domain agents without rewriting orchestration code.

## Problem Statement

Complex tasks often require multiple specialist roles working across sequential stages (planning, implementation, review, etc.). Replicating this pattern today means hard-coding LangGraph state machines or similar orchestration graphs — every new agent type requires core logic changes.

Badger lowers the barrier: **one framework, many agents, YAML-configured roles and stages**.

## Core Requirements

1. **Declarative agent config** — `roles`, `stages`, `steps` defined in YAML; `Flow`, `Stage`, and `Role` provide `name` and `description` for docs and CLI display
2. **Divide-and-conquer collaboration** — prior step outputs available as `{context}` to downstream roles
3. **Pluggable execution** — swap `StepExecutor` for LLM-only, tool-augmented, or mock execution
4. **Built-in reference agents** — naming, debate, requirement review, and code review as pattern examples

## Non-Goals (Current)

- Production sandbox execution (users extend via `StepExecutor`)
- Parallel step execution
- Conditional branching between stages
- Persistent cross-run state (hooks are the extension point)

## Success Criteria

- A user can configure a new agent in YAML and run it via CLI without modifying orchestration code
- Existing built-in agents continue to work unchanged
- `description` fields are usable for CLI/UI display

## Runtime Goals (v2)

- **Extensible**: swap step execution, ordering, and context without touching orchestration core
- **Testable**: mock `StepExecutor` for unit tests without LLM calls
- **Compatible**: same agent YAML schema and `StepOutput`/`RunContext` models as v1
