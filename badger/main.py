from __future__ import annotations

import asyncio
import os
from pathlib import Path

import fire
import yaml
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .engine import FlowEngine, FlowState, StepResult
from .models import AppConfig

console = Console()

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "naming.yaml"


def load_config(path: str | Path | None = None) -> AppConfig:
    env_file = find_dotenv(usecwd=True)
    load_dotenv(env_file)

    path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path) as f:
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

    return AppConfig(**data)


def print_step(step: StepResult) -> None:
    console.print(
        Panel(
            Markdown(step.content),
            title=f"[bold]{step.role}[/bold] — {step.stage}",
            border_style="blue",
        )
    )
    console.print()


async def _async_run(config_path: str | None):
    config = load_config(config_path)
    config_dir = Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent

    console.rule(f"[bold magenta]{config.flow.name or 'Flow'}[/bold magenta]")
    console.print(f"[bold]Model:[/bold] {config.llm.model or 'default'}\n")

    engine = FlowEngine(config, config_dir=config_dir)

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


def run(config: str | None = None):
    """Run the flow engine.

    Args:
        config: Path to config YAML file.
    """
    asyncio.run(_async_run(config))


def main():
    fire.Fire(run)
