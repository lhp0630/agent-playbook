from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from .llm import make_llm
from .models import Flow, Role


class StepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str
    stage: str
    step_index: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FlowState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_input: str = ""
    results: list[StepResult] = Field(default_factory=list)
    current_stage: str = ""
    current_step: int = 0
    is_finished: bool = False


class FlowEngine(Runnable[dict[str, Any], FlowState]):
    def __init__(self, config: Flow):
        self.config = config
        self._last_state: FlowState | None = None

    def _get_role(self, role_name: str) -> Role:
        for role in self.config.roles:
            if role.name == role_name:
                return role

        if role_name == "__moderator__":
            return Role(name="__moderator__")

        raise ValueError(f"Role not found: {role_name}")

    def _make_chain(self, role_name: str, system_prompt: str) -> Runnable:
        role = self._get_role(role_name)
        llm_config = role.llm if role.llm.model else self.config.llm

        # Inject role name and description into system_prompt
        system_prompt = system_prompt.format(
            role_name=role_name,
            role_description=role.description,
        )

        if self.config.instructions:
            system_prompt = f"{self.config.instructions}\n\n{system_prompt}".strip()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{input}"),
            ]
        ).partial(system_prompt=system_prompt)

        return (prompt | make_llm(llm_config, self.config) | StrOutputParser()).with_config(
            run_name=f"step_{role_name}"
        )

    def _build_context(self, state: FlowState) -> str:
        if not state.results:
            return "No previous discussion."

        lines = []
        for r in state.results:
            header = f"[{r.stage}] {r.role}"
            lines.append(f"{header}:\n{r.content}\n")

        return "\n".join(lines)

    async def _execute_steps(self, state: FlowState) -> Iterator[StepResult]:
        for stage in self.config.stages:
            state.current_stage = stage.name

            for i, step in enumerate(stage.steps):
                state.current_step = i
                context = self._build_context(state)
                chain = self._make_chain(step.role, step.system_prompt)

                input_text = step.input.format(
                    topic=state.user_input,
                    user_input=state.user_input,
                    context=context,
                    stage=stage.name,
                )

                content = await chain.ainvoke({"input": input_text})
                result = StepResult(
                    role=step.role,
                    content=content,
                    stage=stage.name,
                    step_index=i,
                )
                state.results.append(result)

                yield result

        state.is_finished = True

    def invoke(self, input: dict[str, Any], config: RunnableConfig | None = None) -> FlowState:
        return asyncio_run(self.ainvoke(input, config))

    async def ainvoke(
        self, input: dict[str, Any], config: RunnableConfig | None = None
    ) -> FlowState:
        user_input = input.get("user_input") or input.get("topic", "")

        if not user_input:
            user_input = self.config.resolve_topic()

        state = FlowState(user_input=user_input)

        async for _ in self._execute_steps(state):
            pass

        self._last_state = state

        return state

    def stream(
        self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ) -> Iterator[StepResult]:
        return asyncio_run(self.astream(input, config, **kwargs))

    async def astream(
        self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ):
        user_input = input.get("user_input") or input.get("topic", "")

        if not user_input:
            user_input = self.config.resolve_topic()

        state = FlowState(user_input=user_input)

        async for result in self._execute_steps(state):
            yield result

        self._last_state = state


def asyncio_run(coro):
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
