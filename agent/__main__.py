import asyncio
import os
import random
import sys
from contextlib import asynccontextmanager
from logging.config import dictConfig
from typing import Any

import fire
import uvicorn
from dotenv import find_dotenv, load_dotenv
from pydantic_ai import Agent
from pydantic_ai.agent.spec import AgentSpec
from pydantic_ai.models import Model
from uvicorn.config import LOGGING_CONFIG

from agent.harness.playbook import Playbook
from agent.harness.playbook._toolset import normalize_models, normalize_name, resolve_models

env_file = find_dotenv(usecwd=True)
load_dotenv(env_file)

from .config import CONFIG_MANAGER  # noqa: E402


def setup_logger(log_level: str = os.getenv("PLAYBOOK_LOG_LEVEL", "INFO")):
    config_logger = {
        **LOGGING_CONFIG,
        "loggers": {
            **LOGGING_CONFIG["loggers"],
            __package__: {"handlers": ["default"], "level": log_level, "propagate": False},
        },
    }
    dictConfig(config_logger)


def _resolve_model_from_spec(spec: AgentSpec) -> list[Model[Any]]:
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
    return resolve_models(None, [])


def startup_web(host: str = "127.0.0.1", port: int = 8000):
    # TODO: Add a runtime update mechanism, or remove the live-reload claim and watcher behavior.
    agent_specs = CONFIG_MANAGER.agent_specs
    if not agent_specs:
        print("No agent spec found.", file=sys.stderr)
        raise SystemExit(1)

    # TODO: Routing Agent that classifies user intent and picks a sub-Agent.
    path, spec = random.choice(agent_specs)

    models = _resolve_model_from_spec(spec)
    if not models and not spec.model:
        print("No model configured for agent.", file=sys.stderr)
        raise SystemExit(1)

    agent = Agent.from_file(
        path,
        custom_capability_types=[Playbook],
        model=models[0] if models else None,
        name=normalize_name(spec.name) if spec.name else None,
    )
    app = agent.to_web(models=models)

    @asynccontextmanager
    async def lifespan(app):
        event = asyncio.Event()
        task = asyncio.create_task(CONFIG_MANAGER.watch_agent_specs(event))

        yield

        event.set()
        await task

    app.router.lifespan_context = lifespan

    setup_logger()
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    fire.Fire(startup_web)


if __name__ == "__main__":
    main()
