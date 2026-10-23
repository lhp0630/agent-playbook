import asyncio
import os
import sys
from contextlib import asynccontextmanager
from logging.config import dictConfig

import fire
import uvicorn
from dotenv import find_dotenv, load_dotenv
from pydantic_ai import Agent
from uvicorn.config import LOGGING_CONFIG

env_file = find_dotenv(usecwd=True)
load_dotenv(env_file)

from .config import CONFIG_MANAGER  # noqa: E402
from .router import (  # noqa: E402
    CUSTOM_CAPABILITY_TYPES,
    AgentRouter,
    load_spec_agent,
    prepare_web_entry,
    router_models,
)


def setup_logger(log_level: str = os.getenv("PLAYBOOK_LOG_LEVEL", "INFO")):
    config_logger = {
        **LOGGING_CONFIG,
        "loggers": {
            **LOGGING_CONFIG["loggers"],
            __package__: {"handlers": ["default"], "level": log_level, "propagate": False},
        },
    }
    dictConfig(config_logger)


def startup_web(host: str = "127.0.0.1", port: int = 8000):
    # TODO: Add a runtime update mechanism, or remove the live-reload claim and watcher behavior.
    try:
        entry = prepare_web_entry(CONFIG_MANAGER.agent_specs)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except SystemExit:
        print("No agent spec found.", file=sys.stderr)
        raise

    if entry.route is not None:
        try:
            agent, models = load_spec_agent(
                entry.route.path,
                custom_capability_types=CUSTOM_CAPABILITY_TYPES,
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
    else:
        models = router_models()
        if not models:
            print("No model configured for agent.", file=sys.stderr)
            raise SystemExit(1)
        agent = Agent(
            models[0],
            name="router",
            capabilities=[
                AgentRouter(
                    specs=lambda: CONFIG_MANAGER.agent_specs,
                    custom_capability_types=CUSTOM_CAPABILITY_TYPES,
                )
            ],
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
