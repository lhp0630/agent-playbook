import re

from pydantic_ai import Agent
from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow

from .llm import make_model
from .models import Flow, Role, Stage


def to_identifier(name: str) -> str:
    """Turn a display name into a valid Python identifier for DynamicWorkflow."""

    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "agent"
    if cleaned[0].isdigit():
        cleaned = f"a_{cleaned}"
    return cleaned.lower()


def _build_role_system_prompts(flow: Flow, role: Role) -> list[str]:
    prompts: list[str] = []
    seen: set[str] = set()
    for stage in flow.stages:
        for step in stage.steps:
            if step.role != role.name or not step.system_prompt.strip():
                continue
            text = step.system_prompt.format(
                role_name=role.name,
                role_description=role.description,
            ).strip()
            if text and text not in seen:
                seen.add(text)
                prompts.append(text)
    return prompts


def _build_role_instructions(flow: Flow, role: Role) -> str:
    prompts: list[str] = [f"You are {role.name}."]
    if role.description.strip():
        prompts.append(role.description.strip())
    if flow.instructions and flow.instructions.strip():
        prompts.append(flow.instructions.strip())
    for prompt in _build_role_system_prompts(flow, role):
        prompts.append(prompt)
    return "\n\n".join(prompts)


def _build_stage_hint(stage: Stage) -> str:
    roles = [step.role for step in stage.steps]
    role_names = ", ".join(dict.fromkeys(roles)) or "(none)"
    desc = stage.description.strip() or "No description."
    return f"- {stage.name} ({role_names}): {desc}"


def _build_instructions(flow: Flow) -> str:
    prompts: list[str] = []

    if flow.description:
        prompts.append(f"You orchestrate a multi-agent workflow: {flow.description.strip()}")

    if flow.instructions and flow.instructions.strip():
        prompts.append(flow.instructions.strip())

    if flow.roles:
        catalog = "\n".join(
            (
                f"- `{to_identifier(role.name)}` ({role.name}): "
                f"{role.description.strip() or 'No description.'}"
            )
            for role in flow.roles
        )
        prompts.append(
            "Use the `run_workflow` tool to coordinate these specialists "
            f"(call each as an async function with `task=...`):\n{catalog}"
        )

    if flow.stages:
        stage_lines = "\n".join(_build_stage_hint(stage) for stage in flow.stages)
        prompts.append(f"Suggested workflow stages:\n{stage_lines}")

    if flow.max_rounds > 1:
        prompts.append(
            f"When a stage is iterative (e.g. debate), run up to {flow.max_rounds} rounds."
        )

    prompts.append(
        "Write a Python script inside `run_workflow` that calls the specialists, "
        "passes prior outputs into later `task` strings, and returns the final result."
    )
    return "\n\n".join(prompts)


def _ensure_moderator(flow: Flow) -> list[Role]:
    """Ensure debate-style `__moderator__` steps have a role entry."""

    roles = list(flow.roles)
    names = {role.name for role in roles}
    needs_moderator = any(
        step.role == "__moderator__" for stage in flow.stages for step in stage.steps
    )
    if needs_moderator and "__moderator__" not in names:
        roles.append(
            Role(
                name="__moderator__",
                description="Moderator who sets topics and keeps the discussion on track.",
            )
        )
    return roles


def build_agent(flow: Flow) -> Agent:
    """Build a pydantic-ai orchestrator with DynamicWorkflow from a Flow config."""

    roles = _ensure_moderator(flow)
    if not roles:
        raise ValueError(f"Flow {flow.name!r} has no roles to orchestrate.")

    default_model = make_model(flow.llm, flow)
    role_agents: list[Agent] = []
    seen: set[str] = set()

    for role in roles:
        ident = to_identifier(role.name)
        if ident in seen:
            raise ValueError(f"Duplicate sub-agent name {ident!r} after normalizing {role.name!r}.")
        seen.add(ident)

        model = make_model(role.llm, flow) if role.llm.model else default_model
        role_agents.append(
            Agent(
                model,
                name=ident,
                description=(role.description.strip() or f"Specialist role: {role.name}"),
                instructions=_build_role_instructions(flow, role),
            )
        )

    return Agent(
        default_model,
        name=to_identifier(flow.name),
        description=flow.description or flow.name,
        instructions=_build_instructions(flow),
        capabilities=[DynamicWorkflow(agents=role_agents)],
    )
