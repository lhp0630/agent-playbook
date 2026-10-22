"""Invariants for the web routing catalog and per-conversation specialist history."""

from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.agent.spec import AgentSpec
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from agent.router import (
    AgentRoute,
    AgentRouter,
    build_agent_catalog,
    prepare_web_entry,
)


def _spec(name: str | None, description: str | None, path: Path) -> tuple[Path, AgentSpec]:
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    return path, AgentSpec.from_dict(data)


def test_catalog_keeps_name_and_description(tmp_path: Path) -> None:
    routes = build_agent_catalog(
        [
            _spec("outlook-mail", "Summarize Outlook mail", tmp_path / "outlook-mail.yaml"),
            _spec("Code Review", "Review a pull request", tmp_path / "code-review.yaml"),
        ]
    )
    assert routes == [
        AgentRoute(
            name="outlook_mail",
            description="Summarize Outlook mail",
            path=tmp_path / "outlook-mail.yaml",
        ),
        AgentRoute(
            name="code_review",
            description="Review a pull request",
            path=tmp_path / "code-review.yaml",
        ),
    ]


def test_catalog_drops_spec_without_description(tmp_path: Path) -> None:
    routes = build_agent_catalog(
        [
            _spec("outlook-mail", "Summarize Outlook mail", tmp_path / "outlook-mail.yaml"),
            _spec("code-review", None, tmp_path / "code-review.yaml"),
            _spec("sandbox", "   ", tmp_path / "sandbox.yaml"),
            _spec(None, "missing name", tmp_path / "anon.yaml"),
        ]
    )
    assert [route.name for route in routes] == ["outlook_mail"]


def test_catalog_rejects_duplicate_normalized_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Duplicate agent name code_review"):
        build_agent_catalog(
            [
                _spec("code-review", "Review a pull request", tmp_path / "a.yaml"),
                _spec("Code Review", "Another review", tmp_path / "b.yaml"),
            ]
        )


def test_single_spec_is_served_directly(tmp_path: Path) -> None:
    entry = prepare_web_entry(
        [_spec("outlook-mail", "Summarize Outlook mail", tmp_path / "outlook-mail.yaml")]
    )
    assert entry.route is not None
    assert entry.route.name == "outlook_mail"


def test_several_specs_use_the_router(tmp_path: Path) -> None:
    entry = prepare_web_entry(
        [
            _spec("outlook-mail", "Summarize Outlook mail", tmp_path / "outlook-mail.yaml"),
            _spec("code-review", "Review a pull request", tmp_path / "code-review.yaml"),
        ]
    )
    assert entry.route is None


def test_empty_catalog_exits() -> None:
    with pytest.raises(SystemExit):
        prepare_web_entry([])


async def test_tool_names_follow_normalized_spec_names(tmp_path: Path) -> None:
    specs = [
        _spec("Code Review", "Review a pull request", tmp_path / "code-review.yaml"),
        _spec("outlook-mail", "Summarize Outlook mail", tmp_path / "outlook-mail.yaml"),
    ]
    for path, spec in specs:
        path.write_text(
            f"name: {spec.name}\ndescription: {spec.description}\n",
            encoding="utf-8",
        )
    router = AgentRouter(specs=lambda: specs)
    active = await router.get_toolset().for_run(None)  # type: ignore[arg-type]
    assert isinstance(active, FunctionToolset)
    assert set(active.tools) == {"code_review", "outlook_mail"}
    assert active.tools["code_review"].description == "Review a pull request"
    assert active.tools["outlook_mail"].description == "Summarize Outlook mail"


async def test_handoff_tool_schema_accepts_only_task(tmp_path: Path) -> None:
    specs = [
        _spec("outlook-mail", "Summarize Outlook mail", tmp_path / "outlook-mail.yaml"),
    ]
    path, spec = specs[0]
    path.write_text(
        f"name: {spec.name}\ndescription: {spec.description}\n",
        encoding="utf-8",
    )
    router = AgentRouter(specs=lambda: specs)
    active = await router.get_toolset().for_run(None)  # type: ignore[arg-type]
    assert isinstance(active, FunctionToolset)
    schema = active.tools["outlook_mail"].function_schema.json_schema
    assert set(schema["properties"]) == {"task"}


class _RecordingModel(TestModel):
    """Records each model request so tests can see the specialist's context."""

    def __init__(self, text: str) -> None:
        super().__init__(custom_output_text=text)
        self.seen: list[list[ModelMessage]] = []

    async def request(self, messages, model_settings, model_request_parameters):  # type: ignore[no-untyped-def]
        self.seen.append(list(messages))
        return await super().request(messages, model_settings, model_request_parameters)


def _rendered(messages: list[ModelMessage]) -> str:
    chunks: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                chunks.append(part.content)
            elif isinstance(part, (ToolCallPart, ToolReturnPart)):
                chunks.append(part.tool_name)
            elif isinstance(part, TextPart):
                chunks.append(part.content)
    return "\n".join(chunks)


def _route(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del info
    text = ""
    for message in reversed(messages):
        if not isinstance(message, ModelRequest):
            continue
        for part in reversed(message.parts):
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                text = part.content
                break
        if text:
            break
    name = "code_review" if "review" in text else "outlook_mail"
    return ModelResponse(
        parts=[ToolCallPart(tool_name=name, args={"task": text}, tool_call_id=f"call-{name}")]
    )


async def test_same_conversation_keeps_each_agent_history(tmp_path: Path) -> None:
    """A later outlook-mail turn does not receive code-review's tool records."""
    specs = [
        _spec("outlook-mail", "Summarize Outlook mail", tmp_path / "outlook-mail.yaml"),
        _spec("code-review", "Review a pull request", tmp_path / "code-review.yaml"),
    ]
    for path, spec in specs:
        path.write_text(
            f"name: {spec.name}\ndescription: {spec.description}\n",
            encoding="utf-8",
        )

    outlook = _RecordingModel("mail-reply")
    review = _RecordingModel("review-reply")

    def loader(route: AgentRoute) -> Agent:
        if route.name == "code_review":
            agent: Agent = Agent(review, name=route.name)

            @agent.tool_plain
            def note_finding(text: str) -> str:
                """Record a review note."""
                return f"noted {text}"

            return agent
        return Agent(outlook, name=route.name)

    router = AgentRouter(specs=lambda: specs, loader=loader)
    agent = Agent(FunctionModel(_route), name="router", capabilities=[router])

    first = await agent.run("list mail", conversation_id="session-a")
    assert first.output == "mail-reply"

    reviewed = await agent.run("review the pr", conversation_id="session-a")
    assert reviewed.output == "review-reply"

    continued = await agent.run("send it", conversation_id="session-a")
    assert continued.output == "mail-reply"

    other = await agent.run("other inbox", conversation_id="session-b")
    assert other.output == "mail-reply"

    assert "list mail" in _rendered(outlook.seen[1])
    assert "send it" in _rendered(outlook.seen[1])
    assert "review the pr" not in _rendered(outlook.seen[1])
    assert "note_finding" not in _rendered(outlook.seen[1])
    assert "note_finding" in _rendered(review.seen[-1])
    assert "other inbox" in _rendered(outlook.seen[2])
    assert "list mail" not in _rendered(outlook.seen[2])
