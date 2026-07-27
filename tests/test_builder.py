from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow

from agent.builder import build_agent, to_identifier
from agent.models import Flow, LlmConfig, Role, Stage, Step


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
    flow = Flow(
        name="Code Review",
        description="Review code",
        llm=LlmConfig(model="gpt-4o-mini", api_key="test-key"),
        instructions="Always respond in Chinese.",
        roles=[
            Role(name="Chen Jie", description="Senior architect."),
        ],
        stages=[
            Stage(
                name="Analysis",
                description="Initial pass",
                steps=[
                    Step(
                        role="Chen Jie",
                        system_prompt="You are {role_name}. {role_description}",
                    )
                ],
            )
        ],
    )

    agent = build_agent(flow)

    assert agent.name == "code_review"
    assert agent.description == "Review code"

    capability = _dynamic_workflow(agent)
    assert len(capability.agents) == 1
    assert capability.agents[0].name == "chen_jie"


def test_build_agent_adds_moderator_role():
    flow = Flow(
        name="Office Debate",
        llm=LlmConfig(model="gpt-4o-mini", api_key="test-key"),
        roles=[Role(name="Alice Chen", description="CTO")],
        stages=[
            Stage(
                name="Topic",
                steps=[Step(role="__moderator__", system_prompt="Generate a topic.")],
            )
        ],
    )

    agent = build_agent(flow)
    names = {entry.name for entry in _dynamic_workflow(agent).agents}
    assert names == {"alice_chen", "moderator"}
