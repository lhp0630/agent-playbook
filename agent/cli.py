from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path

import fire
import yaml
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.segment import Segment
from rich.text import Text

from .engine_v2 import FlowEngine, StepResponse
from .models import Flow

BUILTIN_AGENTS_DIR = Path(__file__).parent / "builtin_agents"

ROLE_WIDTH = 14

console = Console()


_agents: dict[str, Flow] = {}


def _print_step(step: StepResponse, *, current_stage: str, role_width: int = ROLE_WIDTH) -> str:
    if step.stage_name != current_stage:
        current_stage = step.stage_name
        _print_stage_title(step.stage_name)
    _print_role_output(step.role, step.output, role_width=role_width)
    return current_stage


def _trim_leading_segments(line: list[Segment]) -> list[Segment]:
    trimmed: list[Segment] = []
    skipping = True
    for segment in line:
        if skipping:
            stripped = segment.text.lstrip()
            if not stripped:
                continue
            if stripped != segment.text:
                segment = Segment(stripped, segment.style)
            skipping = False
        trimmed.append(segment)
    return trimmed


def _trim_trailing_segments(line: list[Segment]) -> list[Segment]:
    trimmed = list(line)
    while trimmed and not trimmed[-1].text.rstrip():
        trimmed.pop()
    if trimmed:
        last = trimmed[-1]
        stripped = last.text.rstrip()
        if stripped != last.text:
            trimmed[-1] = Segment(stripped, last.style)
    return trimmed


def _normalize_line(line: list[Segment]) -> list[Segment]:
    return _trim_trailing_segments(_trim_leading_segments(line))


def _print_stage_title(stage: str) -> None:
    console.print()
    console.print(f"[reverse]{stage}[/reverse]")
    console.print()


def _print_role_output(role: str, content: str, *, role_width: int = ROLE_WIDTH) -> None:
    markdown = Markdown(content, justify="left")
    content_width = max(console.size.width - role_width, 20)
    lines = console.render_lines(markdown, console.options.update_width(content_width))

    first_line = True
    for line in lines:
        line = _normalize_line(line)

        text = Text()
        if first_line:
            text.append(role.ljust(role_width), style="bold green")
            first_line = False
        else:
            text.append(" " * role_width)

        for segment in line:
            text.append(segment.text, style=segment.style)

        console.print(text)

    console.print()


def _load_agent_config(file: str | Path | None = None) -> Flow:
    env_file = find_dotenv(usecwd=True)
    load_dotenv(env_file)

    if not file:
        raise ValueError("No path provided")

    file = Path(file)

    if not file.exists():
        raise FileNotFoundError(f"Config not found: {file}")

    with open(file) as f:
        kwargs = yaml.safe_load(f) or {}

    llm = kwargs.get("llm") or {}

    if not llm.get("model"):
        llm["model"] = os.getenv("OPENAI_MODEL", "")
    if not llm.get("base_url"):
        llm["base_url"] = os.getenv("OPENAI_BASE_URL", "")
    if not llm.get("api_key"):
        llm["api_key"] = os.getenv("OPENAI_API_KEY", "")

    kwargs["llm"] = llm

    for role in kwargs.get("roles", []):
        if not role.get("llm"):
            role["llm"] = {}

    kwargs["wodk_dir"] = file.parent

    return Flow(**kwargs)


def _load_agents(path: str | Path | None = None) -> None:
    supported_extensions = [".yaml", ".yml"]

    paths: list[Path] = []

    for ext in supported_extensions:
        paths.extend(BUILTIN_AGENTS_DIR.glob(f"*{ext}"))
        if path:
            paths.extend(Path(path).glob(f"*{ext}"))

    paths = [f for f in paths if f.is_file()]

    for config_path in paths:
        try:
            agent = _load_agent_config(config_path)
            _agents[agent.name.lower().replace(" ", "-")] = agent
        except Exception as e:
            console.print(f"[bold red]Error loading agent {config_path}: {e}[/bold red]")


async def arun(name: str | None = None, path: str | None = None) -> None:
    _load_agents(path)

    if not _agents:
        console.print("[bold red]No agents found[/bold red]")
        return

    if not name:
        name = random.choice(list(_agents.keys()))

    agent = _agents.get(name.lower().replace(" ", "-"))
    if not agent:
        console.print(f"[bold red]Agent not found: {name}[/bold red]")
        return

    engine = FlowEngine(agent)
    current_stage = ""

    async for item in engine.astream({}):
        if isinstance(item, StepResponse):
            current_stage = _print_step(item, current_stage=current_stage)

    console.print("[bold green]Done[/bold green]")


def run(name: str | None = None, path: str | None = None) -> None:
    asyncio.run(arun(name, path))


def main() -> None:
    fire.Fire(run)
