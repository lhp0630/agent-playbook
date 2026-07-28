import re

from pydantic_ai import Agent
from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow

from .llm import make_model
from .models import Act, Cast, PlaybookSpec


def to_identifier(name: str) -> str:
    """Turn a display name into a valid Python identifier for DynamicWorkflow."""

    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "agent"
    if cleaned[0].isdigit():
        cleaned = f"a_{cleaned}"
    return cleaned.lower()


def _build_cast_system_prompts(playbook: PlaybookSpec, member: Cast) -> list[str]:
    prompts: list[str] = []
    seen: set[str] = set()
    for act in playbook.acts:
        for cue in act.cues:
            if cue.cast != member.name or not cue.instructions.strip():
                continue
            text = cue.instructions.format(
                role_name=member.name,
                role_description=member.description,
            ).strip()
            if text and text not in seen:
                seen.add(text)
                prompts.append(text)
    return prompts


def _build_cast_instructions(playbook: PlaybookSpec, member: Cast) -> str:
    prompts: list[str] = [f"You are {member.name}."]
    if member.description.strip():
        prompts.append(member.description.strip())
    if playbook.instructions and playbook.instructions.strip():
        prompts.append(playbook.instructions.strip())
    for prompt in _build_cast_system_prompts(playbook, member):
        prompts.append(prompt)
    return "\n\n".join(prompts)


def _build_act_hint(act: Act) -> str:
    casts = [cue.cast for cue in act.cues]
    cast_names = ", ".join(dict.fromkeys(casts)) or "(none)"
    desc = act.description.strip() or "No description."
    return f"- {act.name} ({cast_names}): {desc}"


def _build_instructions(playbook: PlaybookSpec) -> str:
    prompts: list[str] = []

    if playbook.description:
        prompts.append(f"You orchestrate a multi-agent workflow: {playbook.description.strip()}")

    if playbook.instructions and playbook.instructions.strip():
        prompts.append(playbook.instructions.strip())

    if playbook.cast:
        catalog = "\n".join(
            (
                f"- `{to_identifier(member.name)}` ({member.name}): "
                f"{member.description.strip() or 'No description.'}"
            )
            for member in playbook.cast
        )
        prompts.append(
            "Use the `run_workflow` tool to coordinate these specialists "
            f"(call each as an async function with `task=...`):\n{catalog}"
        )

    if playbook.acts:
        act_lines = "\n".join(_build_act_hint(act) for act in playbook.acts)
        prompts.append(f"Suggested workflow acts:\n{act_lines}")

    if playbook.model.max_rounds > 1:
        prompts.append(
            f"When an act is iterative (e.g. debate), run up to {playbook.model.max_rounds} rounds."
        )

    prompts.append(
        "Write a Python script inside `run_workflow` that calls the specialists, "
        "passes prior outputs into later `task` strings, and returns the final result."
    )
    return "\n\n".join(prompts)


def _ensure_moderator(playbook: PlaybookSpec) -> list[Cast]:
    """Ensure debate-style `__moderator__` cues have a cast entry."""

    members = list(playbook.cast)
    names = {member.name for member in members}
    needs_moderator = any(cue.cast == "__moderator__" for act in playbook.acts for cue in act.cues)
    if needs_moderator and "__moderator__" not in names:
        members.append(
            Cast(
                name="__moderator__",
                description="Moderator who sets topics and keeps the discussion on track.",
            )
        )
    return members


def build_agent(playbook: PlaybookSpec) -> Agent:
    """Build a pydantic-ai orchestrator with DynamicWorkflow from a PlaybookSpec."""

    members = _ensure_moderator(playbook)
    if not members:
        raise ValueError(f"Playbook {playbook.name!r} has no cast to orchestrate.")

    default_model = make_model(playbook.model)
    cast_agents: list[Agent] = []
    seen: set[str] = set()

    for member in members:
        ident = to_identifier(member.name)
        if ident in seen:
            raise ValueError(
                f"Duplicate sub-agent name {ident!r} after normalizing {member.name!r}."
            )
        seen.add(ident)

        model = make_model(member.model) if member.model.model else default_model
        cast_agents.append(
            Agent(
                model,
                name=ident,
                description=(member.description.strip() or f"Specialist role: {member.name}"),
                instructions=_build_cast_instructions(playbook, member),
            )
        )

    return Agent(
        default_model,
        name=to_identifier(playbook.name),
        description=playbook.description or playbook.name,
        instructions=_build_instructions(playbook),
        capabilities=[DynamicWorkflow(agents=cast_agents)],
    )
