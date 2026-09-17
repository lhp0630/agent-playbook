import asyncio
import logging
import os
from pathlib import Path

from watchfiles import awatch

from .spec import PlaybookSpec

logger = logging.getLogger(__name__)


class ConfigManager:
    config_path: Path

    _playbooks: list[PlaybookSpec] | None = None

    def __init__(self):
        self.config_path = Path(os.environ.get("PLAYBOOK_CONFIG_PATH", ".agents"))

    @property
    def playbooks(self):
        if not self._playbooks:
            self.load_playbooks()
        assert self._playbooks is not None
        return self._playbooks

    def set_config_path(self, path: Path | str):
        self.config_path = Path(path)
        self.load_playbooks()

    def load_playbooks(self):
        files: list[Path] = []
        for ext in [".yml", ".yaml"]:
            files.extend(self.config_path.glob(f"*{ext}"))

        playbooks: list[PlaybookSpec] = []
        for path in files:
            try:
                playbooks.append(PlaybookSpec.from_yaml(path))
            except Exception as e:
                f"Error loading playbook config {path}: {e}"

        self._playbooks = playbooks

    async def watch_playbooks(self, stop_event: asyncio.Event):
        def verify_playbook_file(path: Path | str):
            return Path(path).suffix.lower() in (".yml", ".yaml")

        async for changes in awatch(self.config_path, recursive=False, stop_event=stop_event):
            if any(verify_playbook_file(p) for _, p in changes):
                logger.info("Playbook config change detected")
                self.load_playbooks()
                logger.info("Reloaded playbook config successfully")


CONFIG_MANAGER = ConfigManager()
