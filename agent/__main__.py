import asyncio
import os
import random
import sys
from contextlib import asynccontextmanager

import fire
import uvicorn
from dotenv import find_dotenv, load_dotenv

from . import make_workflow_agent

env_file = find_dotenv(usecwd=True)
load_dotenv(env_file)

from ._config_manager import CONFIG_MANAGER  # noqa: E402


def setup_logger(log_level: str = os.getenv("PLAYBOOK_LOG_LEVEL", "INFO")):
    from logging.config import dictConfig

    from uvicorn.config import LOGGING_CONFIG

    config_logger = {
        **LOGGING_CONFIG,
        "loggers": {
            **LOGGING_CONFIG["loggers"],
            __package__: {"handlers": ["default"], "level": log_level, "propagate": False},
        },
    }
    dictConfig(config_logger)


def startup_web(name: str | None = None, host: str = "127.0.0.1", port: int = 8000):
    playbooks = CONFIG_MANAGER.playbooks
    if not playbooks:
        print("No playbook found.", file=sys.stderr)
        raise SystemExit(1)

    selected_playbook = (
        random.choice(playbooks)
        if not name
        else next(spec for spec in playbooks if spec.name == name)
    )

    agent = make_workflow_agent(selected_playbook)
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

    print(f"Serving {selected_playbook.name!r} at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    fire.Fire(startup_web)


if __name__ == "__main__":
    main()
