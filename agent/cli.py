from __future__ import annotations

import asyncio
import os
import random
from collections.abc import AsyncIterator
from pathlib import Path

import fire
import yaml
from dotenv import find_dotenv, load_dotenv
from pydantic_ai import AgentRunResultEvent, FunctionToolCallEvent, FunctionToolResultEvent
from rich.console import Console
from rich.markdown import Markdown

from .builder import build_agent
from .models import Flow

BUILTIN_AGENTS_DIR = Path(__file__).parent / "builtin_agents"

console = Console()

_agents: dict[str, Flow] = {}


def _agent_key(name: str) -> str:
    return name.lower().replace(" ", "-")


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

    kwargs["work_dir"] = file.parent
    return Flow(**kwargs)


def _load_agents(path: str | Path | None = None) -> None:
    supported_extensions = [".yaml", ".yml"]
    paths: list[Path] = []

    for ext in supported_extensions:
        paths.extend(BUILTIN_AGENTS_DIR.glob(f"*{ext}"))
        if path:
            paths.extend(Path(path).glob(f"*{ext}"))

    for config_path in (p for p in paths if p.is_file()):
        try:
            agent = _load_agent_config(config_path)
            _agents[_agent_key(agent.name)] = agent
        except Exception as e:
            console.print(f"[bold red]Error loading agent {config_path}: {e}[/bold red]")


async def _consume_events(events: AsyncIterator[object]) -> object | None:
    result = None
    async for event in events:
        if isinstance(event, FunctionToolCallEvent):
            tool = event.part.tool_name
            console.print()
            console.print(f"[reverse]{tool}[/reverse]")
            args = event.part.args
            if tool == "run_workflow" and isinstance(args, dict) and args.get("code"):
                console.print(Markdown(f"```python\n{args['code']}\n```"))
            console.print()
        elif isinstance(event, FunctionToolResultEvent):
            console.print("[dim]tool finished[/dim]")
            console.print()
        elif isinstance(event, AgentRunResultEvent):
            result = event.result
    return result


async def arun(name: str | None = None, path: str | None = None) -> None:
    _load_agents(path)

    if not _agents:
        console.print("[bold red]No agents found[/bold red]")
        return

    if not name:
        name = random.choice(list(_agents.keys()))

    flow = _agents.get(_agent_key(name))
    if not flow:
        console.print(f"[bold red]Agent not found: {name}[/bold red]")
        console.print(f"Available: {', '.join(sorted(_agents))}")
        return

    console.print(f"[bold]{flow.name}[/bold]")
    if flow.description:
        console.print(f"[dim]{flow.description}[/dim]")
    console.print()

    agent = build_agent(flow)
    user_prompt = flow.resolve_topic() or (
        f"Run the '{flow.name}' workflow using the available specialists."
    )

    async with agent.run_stream_events(user_prompt) as events:
        result = await _consume_events(events)

    console.print()
    output = getattr(result, "output", None) if result is not None else None
    if output and (not isinstance(output, str) or output.strip()):
        console.print(Markdown(str(output)))
    console.print()
    console.print("[bold green]Done[/bold green]")


def run(name: str | None = None, path: str | None = None) -> None:
    asyncio.run(arun(name, path))


def main() -> None:
    fire.Fire(run)
