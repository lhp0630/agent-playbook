from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any, Protocol, runtime_checkable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from .llm import make_llm
from .models import Flow, Role, Stage, Step

# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------


class StepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_name: str
    role: str
    output: str


class RunContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str = ""
    reponses: list[StepResponse] = Field(default_factory=list)


def asyncio_run(coro: Any) -> Any:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()

    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Step execution request / hooks
# ---------------------------------------------------------------------------


class StepRequest(BaseModel):
    """Immutable snapshot passed to a StepExecutor for one step invocation."""

    model_config = ConfigDict(extra="forbid")

    flow: Flow
    stage: Stage
    step: Step
    run_context: RunContext
    context: str = ""


StepHook = Callable[[StepRequest, StepResponse | None], Awaitable[None] | None]
ErrorHook = Callable[[StepRequest, BaseException], Awaitable[None] | None]


class EngineHooks(BaseModel):
    """Lifecycle callbacks invoked by FlowEngine during execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    on_step_start: StepHook | None = None
    on_step_end: StepHook | None = None
    on_step_error: ErrorHook | None = None


# ---------------------------------------------------------------------------
# Pluggable components
# ---------------------------------------------------------------------------


@runtime_checkable
class ContextBuilder(Protocol):
    def build(self, state: RunContext) -> str: ...


class DefaultContextBuilder:
    """Builds a textual transcript from completed steps."""

    def build(self, state: RunContext) -> str:
        if not state.reponses:
            return "No previous discussion."

        lines: list[str] = []
        for record in state.reponses:
            header = f"[{record.stage_name}] {record.role}"
            lines.append(f"{header}:\n{record.output}\n")

        return "\n".join(lines)


@runtime_checkable
class StepExecutor(Protocol):
    async def execute(self, request: StepRequest) -> StepResponse: ...


class LlmStepExecutor:
    """Default StepExecutor: one LLM call per step via LangChain."""

    def __init__(self, flow: Flow) -> None:
        self._flow = flow

    def _get_role(self, name: str) -> Role:
        for role in self._flow.roles:
            if role.name == name:
                return role

        if name == "__moderator__":
            return Role(name="__moderator__")

        raise ValueError(f"Role not found: {name}")

    def _make_chain(self, role_name: str, system_prompt: str) -> Runnable:
        role = self._get_role(role_name)
        llm_config = role.llm if role.llm.model else self._flow.llm

        system_prompt = system_prompt.format(
            role_name=role_name,
            role_description=role.description,
        )

        if self._flow.instructions:
            system_prompt = f"{self._flow.instructions}\n\n{system_prompt}".strip()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{input}"),
            ]
        ).partial(system_prompt=system_prompt)

        return (prompt | make_llm(llm_config, self._flow) | StrOutputParser()).with_config(
            run_name=f"step_{role_name}"
        )

    async def execute(self, request: StepRequest) -> StepResponse:
        chain = self._make_chain(request.step.role, request.step.system_prompt)

        step_input = request.step.input.format(
            topic=request.run_context.input,
            user_input=request.run_context.input,
            context=request.context,
            stage=request.stage.name,
        )

        content = await chain.ainvoke({"input": step_input})
        return StepResponse(
            role=request.step.role,
            output=content,
            stage_name=request.stage.name,
        )


@runtime_checkable
class ExecutionPlan(Protocol):
    def iter_steps(self, flow: Flow) -> Iterator[tuple[Stage, Step]]: ...


class SequentialExecutionPlan:
    """Default plan: walk stages in order, then steps within each stage."""

    def iter_steps(self, flow: Flow) -> Iterator[tuple[Stage, Step]]:
        for stage in flow.stages:
            for step in stage.steps:
                yield stage, step


class RepeatingStageExecutionPlan:
    """Repeat every stage (except the first) for `rounds` total debate rounds.

    The first stage is assumed to be setup (e.g. topic generation) and runs once.
    Remaining stages repeat `max_rounds` times from the flow config.
    """

    def iter_steps(self, flow: Flow) -> Iterator[tuple[Stage, Step]]:
        if not flow.stages:
            return

        yield from ((flow.stages[0], step) for step in flow.stages[0].steps)

        debate_stages = flow.stages[1:]
        for _ in range(flow.max_rounds):
            for stage in debate_stages:
                for step in stage.steps:
                    yield stage, step


# ---------------------------------------------------------------------------
# Generic flow engine skeleton
# ---------------------------------------------------------------------------


class FlowEngine(Runnable[dict[str, Any], RunContext]):
    """Generic engine skeleton for executing Flow configurations.

    Orchestration is separated from step execution so callers can swap:
    - *ExecutionPlan* — stage/step ordering (sequential, repeating, …)
    - *StepExecutor* — how a single step runs (LLM, tool call, mock, …)
    - *ContextBuilder* — how prior steps are summarized for the next step
    - *EngineHooks* — lifecycle callbacks for logging, UI, metrics, …
    """

    def __init__(
        self,
        flow: Flow,
        *,
        step_executor: StepExecutor | None = None,
        context_builder: ContextBuilder | None = None,
        execution_plan: ExecutionPlan | None = None,
        hooks: EngineHooks | None = None,
    ) -> None:
        self.flow = flow
        self.step_executor = step_executor or LlmStepExecutor(flow)
        self.context_builder = context_builder or DefaultContextBuilder()
        self.execution_plan = execution_plan or SequentialExecutionPlan()
        self.hooks = hooks or EngineHooks()
        self._last_state: RunContext | None = None

    def _resolve_input(self, input: dict[str, Any]) -> str:
        user_input = input.get("user_input") or input.get("topic", "")
        if not user_input:
            user_input = self.flow.resolve_topic()
        return user_input

    async def _invoke_hook(
        self,
        hook: StepHook | ErrorHook | None,
        *args: Any,
    ) -> None:
        if hook is None:
            return

        result = hook(*args)
        if result is not None:
            await result

    async def _run(self, run_context: RunContext) -> AsyncIterator[StepResponse]:
        for stage, step in self.execution_plan.iter_steps(self.flow):
            request = StepRequest(
                flow=self.flow,
                stage=stage,
                step=step,
                run_context=run_context,
                context=self.context_builder.build(run_context),
            )

            await self._invoke_hook(self.hooks.on_step_start, request, None)

            try:
                output = await self.step_executor.execute(request)
            except BaseException as exc:
                await self._invoke_hook(self.hooks.on_step_error, request, exc)
                raise

            run_context.reponses.append(output)
            await self._invoke_hook(self.hooks.on_step_end, request, output)
            yield output

    def invoke(self, input: dict[str, Any], config: RunnableConfig | None = None) -> RunContext:
        return asyncio_run(self.ainvoke(input, config))

    async def ainvoke(
        self, input: dict[str, Any], config: RunnableConfig | None = None
    ) -> RunContext:
        run_ctx = RunContext(input=self._resolve_input(input))

        async for _ in self._run(run_ctx):
            pass

        self._last_state = run_ctx
        return run_ctx

    def stream(
        self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ) -> Iterator[StepResponse]:
        return asyncio_run(self.astream(input, config, **kwargs))

    async def astream(
        self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ) -> AsyncIterator[StepResponse]:
        run_ctx = RunContext(input=self._resolve_input(input))

        async for result in self._run(run_ctx):
            yield result

        self._last_state = run_ctx
