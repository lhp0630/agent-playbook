from __future__ import annotations

import pytest

from agent.engine_v2 import (
    DefaultContextBuilder,
    EngineHooks,
    FlowEngine,
    RepeatingStageExecutionPlan,
    RunContext,
    SequentialExecutionPlan,
    StepRequest,
    StepResponse,
)
from agent.models import Flow, Stage, Step


class RecordingExecutor:
    def __init__(self, outputs: list[str] | None = None) -> None:
        self.outputs = outputs or []
        self.requests: list[StepRequest] = []

    async def execute(self, request: StepRequest) -> StepResponse:
        self.requests.append(request)
        index = len(self.requests) - 1
        text = self.outputs[index] if index < len(self.outputs) else f"output-{index}"
        return StepResponse(role=request.step.role, output=text, stage_name=request.stage.name)


def _make_flow(*, max_rounds: int = 1) -> Flow:
    return Flow(
        name="test",
        topic="hello topic",
        max_rounds=max_rounds,
        stages=[
            Stage(
                name="setup",
                steps=[Step(role="Alice", system_prompt="", input="topic={topic}")],
            ),
            Stage(
                name="debate",
                steps=[
                    Step(role="Alice", system_prompt="", input="{context}"),
                    Step(role="Bob", system_prompt="", input="{context}"),
                ],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_sequential_plan_executes_all_steps():
    executor = RecordingExecutor(["a", "b", "c"])
    engine = FlowEngine(_make_flow(), step_executor=executor)

    results = [item async for item in engine.astream({})]

    assert len(results) == 3
    assert [r.output for r in results] == ["a", "b", "c"]
    assert executor.requests[1].context.startswith("[setup] Alice")


@pytest.mark.asyncio
async def test_repeating_plan_repeats_debate_stage():
    executor = RecordingExecutor()
    engine = FlowEngine(
        _make_flow(max_rounds=2),
        step_executor=executor,
        execution_plan=RepeatingStageExecutionPlan(),
    )

    results = [item async for item in engine.astream({})]

    # setup (1) + debate (2 steps) * 2 rounds = 5
    assert len(results) == 5
    assert [r.stage_name for r in results] == [
        "setup",
        "debate",
        "debate",
        "debate",
        "debate",
    ]


def test_default_context_builder():
    state = RunContext(
        input="topic",
        reponses=[
            StepResponse(stage_name="s1", role="Alice", output="first"),
            StepResponse(stage_name="s2", role="Bob", output="second"),
        ],
    )

    text = DefaultContextBuilder().build(state)

    assert "[s1] Alice" in text
    assert "first" in text
    assert "[s2] Bob" in text


@pytest.mark.asyncio
async def test_hooks_fire_on_step_lifecycle():
    events: list[str] = []

    async def on_start(request: StepRequest, _: StepResponse | None) -> None:
        events.append(f"start:{request.step.role}")

    async def on_end(request: StepRequest, output: StepResponse | None) -> None:
        events.append(f"end:{output.output if output else ''}")

    hooks = EngineHooks(on_step_start=on_start, on_step_end=on_end)
    engine = FlowEngine(
        _make_flow(),
        step_executor=RecordingExecutor(["only"]),
        hooks=hooks,
    )

    await engine.ainvoke({})

    assert events == [
        "start:Alice",
        "end:only",
        "start:Alice",
        "end:output-1",
        "start:Bob",
        "end:output-2",
    ]


def test_sequential_plan_iteration():
    flow = _make_flow()
    pairs = list(SequentialExecutionPlan().iter_steps(flow))
    assert len(pairs) == 3
    assert pairs[0][0].name == "setup"
