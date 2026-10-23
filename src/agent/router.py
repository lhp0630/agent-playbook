"""Route a web chat turn to one loaded agent spec.

The routing agent is the only web entry when several specs are loaded. Each
specialist keeps its own message history for a conversation, so a later handoff
does not carry another agent's tool records.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai._agent_graph import CallToolsNode, ModelRequestNode
from pydantic_ai._utils import fill_run_metadata
from pydantic_ai.agent.spec import AgentSpec
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.result import FinalResult
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset
from pydantic_graph import End

from harness.open_sandbox import OpenSandbox
from harness.playbook import Playbook
from harness.playbook._toolset import normalize_models, normalize_name, resolve_models

CUSTOM_CAPABILITY_TYPES: list[type[AbstractCapability[Any]]] = [Playbook, OpenSandbox]

ROUTER_INSTRUCTIONS = """
You route each user message to one agent.
Answer by calling one tool, or by asking a clarifying question.
Each tool is one agent. Call the tool whose description matches the message.
Pass the user's request as task and keep URLs, paths, and explicit confirmations.
If an earlier turn in this chat already called an agent and this message continues that task,
call the same tool again.
If two tools could fit, ask one clarifying question and do not call a tool.
If none fit, list the tool descriptions and ask the user to choose.
If the message asks for two different tasks, call the tool for the first and say the other
needs another message.
After a tool returns, that result is the reply to the user.
""".strip()


@dataclass(frozen=True)
class AgentRoute:
    """One loaded spec the router can hand a turn to."""

    name: str
    description: str
    path: Path


@dataclass(frozen=True)
class WebEntry:
    """How to serve the loaded specs.

    `route` is set when exactly one spec is loaded and should be served directly.
    It is None when the routing agent is the web entry.
    """

    route: AgentRoute | None


def build_agent_catalog(specs: Sequence[tuple[Path, AgentSpec]]) -> list[AgentRoute]:
    """Build the routing catalog from loaded specs.

    Specs without a name or description are omitted: the model selects a tool by
    that description. Two specs that normalize to the same name would be the same
    tool, so that is an error.
    """
    routes: list[AgentRoute] = []
    seen: dict[str, Path] = {}
    for path, spec in specs:
        if not spec.name:
            continue
        description = str(spec.description).strip() if spec.description else ""
        if not description:
            continue
        name = normalize_name(spec.name)
        previous = seen.get(name)
        if previous is not None:
            raise ValueError(
                f"Duplicate agent name {name} after normalizing {spec.name!r} "
                f"({path}) and {previous}."
            )
        seen[name] = path
        routes.append(AgentRoute(name=name, description=description, path=path))
    return routes


def prepare_web_entry(specs: Sequence[tuple[Path, AgentSpec]]) -> WebEntry:
    """Choose the web entry for the loaded specs.

    An empty catalog means there is nothing to serve.
    """
    routes = build_agent_catalog(specs)
    if not routes:
        raise SystemExit(1)
    if len(routes) == 1:
        return WebEntry(route=routes[0])
    return WebEntry(route=None)


def resolve_models_for_spec(spec: AgentSpec) -> list[Model[Any]]:
    """Prefer Playbook-configured models; fall back to OPENAI_* env vars."""
    # TODO: Read models/model_providers from app_config and pass them into Playbook
    # instead of pulling them from the playbook capability kwargs / OPENAI_* env.
    for cap in spec.capabilities:
        if cap.name != "Playbook":
            continue
        kwargs = cap.kwargs
        models = resolve_models(
            normalize_models(kwargs.get("models")),
            kwargs.get("model_providers") or [],
        )
        if models:
            return models
    # Only reads OPENAI_* env vars.
    return resolve_models(None, [])


def load_spec_agent(
    path: Path,
    *,
    custom_capability_types: Sequence[type[AbstractCapability[Any]]] = (),
) -> tuple[Agent[Any, Any], list[Model[Any]]]:
    """Build the specialist agent for one spec file."""
    spec = AgentSpec.from_file(path)
    models = resolve_models_for_spec(spec)
    if not models and not spec.model:
        raise RuntimeError(f"No model configured for agent {spec.name!r}.")
    agent = Agent.from_file(
        path,
        custom_capability_types=list(custom_capability_types),
        model=models[0] if models else None,
        name=normalize_name(spec.name) if spec.name else None,
    )
    return agent, models


def _file_fingerprint(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


class SpecialistHistories:
    """Per-conversation message history for each specialist.

    The key is `(conversation_id, agent_name)`. A handoff reads and appends only
    that list, so one agent's tool records stay out of the other's model context.
    """

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], list[ModelMessage]] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def lock(self, conversation_id: str, agent_name: str) -> asyncio.Lock:
        key = (conversation_id, agent_name)
        async with self._guard:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def snapshot(self, conversation_id: str, agent_name: str) -> list[ModelMessage]:
        return list(self._items.get((conversation_id, agent_name), []))

    def append(
        self,
        conversation_id: str,
        agent_name: str,
        messages: Sequence[ModelMessage],
    ) -> None:
        if not messages:
            return
        self._items.setdefault((conversation_id, agent_name), []).extend(messages)


class SpecialistPool:
    """One specialist agent per spec fingerprint.

    A changed spec file is loaded again on the next handoff. Concurrent runs of
    the same agent share the instance; conversation history is not stored on it.
    """

    def __init__(
        self,
        *,
        custom_capability_types: Sequence[type[AbstractCapability[Any]]],
        loader: Callable[[AgentRoute], Agent[Any, Any]] | None = None,
    ) -> None:
        self._custom_capability_types = custom_capability_types
        self._loader = loader
        self._agents: dict[tuple[str, tuple[int, int]], Agent[Any, Any]] = {}

    def get(self, route: AgentRoute) -> Agent[Any, Any]:
        fingerprint = _file_fingerprint(route.path)
        key = (route.name, fingerprint)
        cached = self._agents.get(key)
        if cached is not None:
            return cached
        self._agents = {k: agent for k, agent in self._agents.items() if k[0] != route.name}
        if self._loader is not None:
            agent = self._loader(route)
        else:
            agent, _models = load_spec_agent(
                route.path,
                custom_capability_types=self._custom_capability_types,
            )
        self._agents[key] = agent
        return agent


def _make_handoff(router: AgentRouter, route: AgentRoute):
    """Bind the target agent outside the tool signature.

    pydantic-ai publishes every parameter except ``RunContext`` in the tool schema.
    A ``route`` parameter would let the model supply its own path and load an arbitrary spec.
    """

    async def handoff(ctx: RunContext[Any], task: str) -> str:
        """Hand the user request to this agent.

        Args:
            task: The user request, including URLs and explicit confirmations.
        """
        return await router.handoff(ctx, route, task)

    return handoff


def _router_function_toolset(
    router: AgentRouter,
    routes: Sequence[AgentRoute],
) -> FunctionToolset[Any]:
    toolset: FunctionToolset[Any] = FunctionToolset(id="agent-router", sequential=True)
    for route in routes:
        toolset.add_function(
            _make_handoff(router, route),
            name=route.name,
            description=route.description,
            sequential=True,
        )
    return toolset


class AgentRouterToolset(FunctionToolset[Any]):
    """Expose one handoff tool per catalog entry for this run."""

    def __init__(self, router: AgentRouter) -> None:
        super().__init__(id="agent-router", sequential=True)
        self._router = router

    async def for_run(self, ctx: RunContext[Any]) -> AbstractToolset[Any]:
        routes = build_agent_catalog(self._router.specs())
        return _router_function_toolset(self._router, routes)


@dataclass(kw_only=True)
class AgentRouter(AbstractCapability[Any]):
    """Handoff tools for the loaded agent specs, plus each specialist's history."""

    specs: Callable[[], Sequence[tuple[Path, AgentSpec]]]
    custom_capability_types: Sequence[type[AbstractCapability[Any]]] = ()
    loader: Callable[[AgentRoute], Agent[Any, Any]] | None = None
    histories: SpecialistHistories = field(default_factory=SpecialistHistories)

    _pool: SpecialistPool = field(init=False, repr=False)
    _handoffs: dict[str | None, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._pool = SpecialistPool(
            custom_capability_types=self.custom_capability_types,
            loader=self.loader,
        )

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None

    def get_instructions(self) -> str:
        return ROUTER_INSTRUCTIONS

    def get_toolset(self) -> AgentRouterToolset:
        return AgentRouterToolset(self)

    async def handoff(self, ctx: RunContext[Any], route: AgentRoute, task: str) -> str:
        """Run the specialist with this conversation's history for that agent only."""
        conversation_id = ctx.conversation_id or ctx.run_id or ""
        agent = self._pool.get(route)
        lock = await self.histories.lock(conversation_id, route.name)
        async with lock:
            history = self.histories.snapshot(conversation_id, route.name)
            result = await agent.run(task, message_history=history)
            self.histories.append(conversation_id, route.name, result.new_messages())
        output = result.output if isinstance(result.output, str) else str(result.output)
        self._handoffs.setdefault(ctx.run_id, output)
        return output

    async def after_node_run(
        self,
        ctx: RunContext[Any],
        *,
        node: Any,
        result: Any,
    ) -> Any:
        """Use the specialist reply as this turn's output.

        The tool return is appended first so the router transcript kept by to_web
        still shows which agent was called.
        """
        if not isinstance(node, CallToolsNode):
            return result
        output = self._handoffs.pop(ctx.run_id, None)
        if output is None:
            return result
        if isinstance(result, ModelRequestNode):
            fill_run_metadata(
                result.request,
                run_id=ctx.run_id,
                conversation_id=ctx.conversation_id,
            )
            ctx.messages.append(result.request)
        return End(FinalResult(output))


def router_models() -> list[Model[Any]]:
    """Model for the routing agent."""
    # Only reads OPENAI_* env vars.
    return resolve_models(None, [])
