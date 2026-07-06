from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv

from .engine import FlowEngine, FlowState, StepResult
from .models import Flow
from .ui import console, print_step

BUILTIN_FLOWS_DIR = Path(__file__).parent / "builtin_flows"


_flows: dict[str, Flow] = {}


def _load_config(file: str | Path | None = None) -> Flow:
    env_file = find_dotenv(usecwd=True)
    load_dotenv(env_file)

    if not file:
        raise ValueError("No path provided")

    file = Path(file)

    if not file.exists():
        raise FileNotFoundError(f"Config not found: {file}")

    with open(file) as f:
        data = yaml.safe_load(f) or {}

    # Env vars fill empty values (lower priority than yaml)
    llm = data.get("llm") or {}

    if not llm.get("model"):
        llm["model"] = os.getenv("OPENAI_MODEL", "")
    if not llm.get("base_url"):
        llm["base_url"] = os.getenv("OPENAI_BASE_URL", "")
    if not llm.get("api_key"):
        llm["api_key"] = os.getenv("OPENAI_API_KEY", "")

    data["llm"] = llm

    # Fix YAML None for empty llm blocks in roles
    for role in data.get("roles", []):
        if not role.get("llm"):
            role["llm"] = {}

    data["wodk_dir"] = file.parent

    return Flow(**data)


def _load_flows(path: str | Path | None = None):
    supported_extensions = [".yaml", ".yml"]

    paths: list[Path] = []

    for s in supported_extensions:
        paths.extend(BUILTIN_FLOWS_DIR.glob(f"*{s}"))
        if path:
            paths.extend(Path(path).glob(f"*{s}"))

    paths = [f for f in paths if f.is_file()]

    for path in paths:
        try:
            flow = _load_config(path)
            _flows[flow.name.lower().replace(" ", "-")] = flow
        except Exception as e:
            console.print(f"[bold red]Error loading flow {path}: {e}[/bold red]")


async def arun(name: str | None = None, path: str | None = None):
    _load_flows(path)

    if not name:
        name = random.choice(list(_flows.keys()))

    flow = _flows.get(name.lower().replace(" ", "-"))
    if not flow:
        console.print(f"[bold red]Flow not found: {name}[/bold red]")
        return

    console.rule(f"[bold magenta]{flow.name or 'Flow'}[/bold magenta]")
    # console.print(f"[bold]Model:[/bold] {flow.llm.model or 'default'}\n")
    console.print("[bold]Model:[/bold] gpt-4o-mini\n")

    engine = FlowEngine(flow)

    current_stage = ""
    async for item in engine.astream({}):
        if isinstance(item, StepResult):
            if item.stage != current_stage:
                current_stage = item.stage
                console.rule(f"[bold yellow]{current_stage}[/bold yellow]")

            print_step(item)

    state = engine._last_state or FlowState()

    console.rule("[bold green]Complete[/bold green]")
    console.print(f"[bold]Total steps:[/bold] {len(state.results)}")


def run(name: str | None = None, path: str | None = None):
    asyncio.run(arun(name, path))
