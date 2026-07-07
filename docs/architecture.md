# Architecture

## Overview

Badger is a **declarative multi-agent divide-and-conquer agent framework**. Complex tasks are decomposed into specialist roles and sequential stages, all defined in YAML — no hard-coded orchestration graph required. Each YAML file defines one agent; swapping the config defines a new domain agent.

## Divide-and-Conquer Pattern

Badger models collaborative work as specialist agents passing context across sequential stages:

```
Task → [Agent₁ → Agent₂ → … → Agentₙ] → Output
         ↑____________context___________|
```

- **Role** — a specialist agent persona (e.g. Planner, Programmer, Reviewer)
- **Stage** — an ordered group containing one or more **Steps**
- **Step** — one execution of a Role within a stage; prior outputs are summarized by `ContextBuilder` into `{context}` for downstream steps

The same orchestration runtime supports different domain agents (coding, requirement review, debate, naming, etc.) — swap the YAML; no core code changes required.

## Runtime Layers

```
Agent config (YAML) → FlowEngine → ExecutionPlan → StepExecutor → LLM / Tools
                            ↓
                  ContextBuilder + EngineHooks
```

`FlowEngine` is the internal orchestration runtime. Users define agents via YAML config; they do not call the runtime API directly.

## Orchestration Runtime (`engine_v2.py`)

`FlowEngine` exposes four pluggable extension points:

| Component | Default | Purpose |
|-----------|---------|---------|
| `ExecutionPlan` | `SequentialExecutionPlan` | Stage/step ordering |
| `StepExecutor` | `LlmStepExecutor` | How one step runs |
| `ContextBuilder` | `DefaultContextBuilder` | Prior-step transcript |
| `EngineHooks` | empty | Lifecycle callbacks |

`Engine` is an alias for `FlowEngine`. `RepeatingStageExecutionPlan` repeats post-setup stages `max_rounds` times (for debate agents).

## Data Flow

1. `FlowEngine._resolve_input()` resolves user/topic input
2. `ExecutionPlan.iter_steps()` yields `(Stage, Step)` pairs in order
3. `ContextBuilder.build()` summarizes completed step outputs
4. `StepExecutor.execute(StepRequest)` runs one step and returns `StepOutput`
5. Hooks fire at step start, end, and error

## Agent Config Schema

Top-level `Flow` fields (see `models.py`) — one YAML file = one agent:

| Field | Purpose |
|-------|---------|
| `name` | Agent identifier for CLI `-n` |
| `description` | Human-readable agent summary |
| `roles` | Specialist personas (`name`, `description`, optional per-role `llm`) |
| `stages` | Ordered stage list; each stage has `steps` binding a `role` with prompts |
| `topic` | Task input: empty, string, or `file:path` |
| `instructions` | Global prompt appended to every step |

Config details and template variables are in [technical.md](technical.md).

## Compatibility

- `Engine` is an alias for `FlowEngine`
- CLI and UI import from `engine_v2`
