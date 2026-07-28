from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow

from agent.builder import build_agent, to_identifier
from agent.models import Act, Cast, Cue, ModelConfig, PlaybookSpec


def _dynamic_workflow(orchestrator) -> DynamicWorkflow:
    for capability in orchestrator.root_capability.capabilities:
        if isinstance(capability, DynamicWorkflow):
            return capability
    raise AssertionError("DynamicWorkflow capability not found")


def test_to_identifier_normalizes_display_names():
    assert to_identifier("Chen Jie") == "chen_jie"
    assert to_identifier("Alice Chen") == "alice_chen"
    assert to_identifier("__moderator__") == "moderator"
    assert to_identifier("123bad") == "a_123bad"


def test_build_agent_wires_roles():
    playbook = PlaybookSpec(
        name="Code Review",
        description="Review code",
        model=ModelConfig(model="gpt-4o-mini", api_key="test-key", temperature=0.3),
        instructions="Always respond in Chinese.",
        cast=[
            Cast(name="Chen Jie", description="Senior architect."),
        ],
        acts=[
            Act(
                name="Analysis",
                description="Initial pass",
                cues=[
                    Cue(
                        cast="Chen Jie",
                        instructions="You are {role_name}. {role_description}",
                    )
                ],
            )
        ],
    )

    agent = build_agent(playbook)

    assert agent.name == "code_review"
    assert agent.description == "Review code"

    capability = _dynamic_workflow(agent)
    assert len(capability.agents) == 1
    assert capability.agents[0].name == "chen_jie"


def test_build_agent_adds_moderator_role():
    playbook = PlaybookSpec(
        name="Office Debate",
        model=ModelConfig(model="gpt-4o-mini", api_key="test-key", max_rounds=3),
        cast=[Cast(name="Alice Chen", description="CTO")],
        acts=[
            Act(
                name="Topic",
                cues=[Cue(cast="__moderator__", instructions="Generate a topic.")],
            )
        ],
    )

    agent = build_agent(playbook)
    names = {entry.name for entry in _dynamic_workflow(agent).agents}
    assert names == {"alice_chen", "moderator"}
