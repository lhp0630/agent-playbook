import asyncio
import logging
import os
from pathlib import Path

from watchfiles import awatch

from agent.playbook_spec import PlaybookSpec

logger = logging.getLogger(__name__)


class ConfigManager:
    config_path: Path

    _agent_specs: list[tuple[Path, PlaybookSpec]] | None = None

    def __init__(self):
        self.config_path = Path(os.environ.get("PLAYBOOK_CONFIG_PATH", ".agents"))

    @property
    def agent_specs(self) -> list[tuple[Path, PlaybookSpec]]:
        if not self._agent_specs:
            self.load_agent_specs()
        assert self._agent_specs is not None
        return self._agent_specs

    def set_config_path(self, path: Path | str):
        self.config_path = Path(path)
        self.load_agent_specs()

    def load_agent_specs(self):
        files: list[Path] = []
        for ext in [".yml", ".yaml"]:
            files.extend(self.config_path.glob(f"*{ext}"))

        specs: list[tuple[Path, PlaybookSpec]] = []
        for path in files:
            try:
                if not path.is_file():
                    raise FileNotFoundError()
                specs.append((path, PlaybookSpec.from_file(path)))
            except Exception as e:
                logger.error("Error loading agent spec %s: %s", path, e)

        self._agent_specs = specs

    async def watch_agent_specs(self, stop_event: asyncio.Event):
        def verify_spec_file(path: Path | str):
            return Path(path).suffix.lower() in (".yml", ".yaml")

        async for changes in awatch(self.config_path, recursive=False, stop_event=stop_event):
            if any(verify_spec_file(p) for _, p in changes):
                logger.info("Agent spec change detected")
                self.load_agent_specs()
                logger.info("Reloaded agent specs successfully")


CONFIG_MANAGER = ConfigManager()
