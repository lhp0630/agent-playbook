import asyncio
import os
import random
import sys
from contextlib import asynccontextmanager
from logging.config import dictConfig

import fire
import uvicorn
from dotenv import find_dotenv, load_dotenv
from pydantic_ai import Agent
from pydantic_ai.capabilities import WebFetch
from uvicorn.config import LOGGING_CONFIG

from agent.harness.playbook._toolset import normalize_name

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


def startup_web(name: str | None = None, host: str = "127.0.0.1", port: int = 8000):
    # TODO: Add a runtime update mechanism, or remove the live-reload claim and watcher behavior.
    playbooks = CONFIG_MANAGER.playbooks
    if not playbooks:
        print("No playbook found.", file=sys.stderr)
        raise SystemExit(1)

    selected_playbook = (
        random.choice(playbooks) if not name else next(pb for pb in playbooks if pb.name == name)
    )

    models = selected_playbook.resolve_models()
    if not models:
        print("No model configured for playbook.", file=sys.stderr)
        raise SystemExit(1)

    agent = Agent(
        model=models[0],
        name=normalize_name(selected_playbook.name),
        description=selected_playbook.description,
        model_settings=selected_playbook.model_settings,
        capabilities=[
            WebFetch(local=True),
            selected_playbook,
        ],
    )
    app = agent.to_web()

    @asynccontextmanager
    async def lifespan(app):
        event = asyncio.Event()
        task = asyncio.create_task(CONFIG_MANAGER.watch_playbooks(event))

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
