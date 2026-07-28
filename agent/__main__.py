import random
import sys
from pathlib import Path

import fire
import uvicorn
from dotenv import find_dotenv, load_dotenv

from .builder import build_agent
from .models import PlaybookSpec

BUILTIN_AGENTS_DIR = Path(__file__).parent / "builtin_agents"


def _load_playbook_specs(path: str | Path | None = None) -> list[PlaybookSpec]:
    env_file = find_dotenv(usecwd=True)
    load_dotenv(env_file)

    supported_extensions = [".yaml", ".yml"]
    paths: list[Path] = []

    playbook_specs: list[PlaybookSpec] = []

    for ext in supported_extensions:
        paths.extend(BUILTIN_AGENTS_DIR.glob(f"*{ext}"))
        if path:
            paths.extend(Path(path).glob(f"*{ext}"))

    for spec_path in (p for p in paths if p.is_file()):
        try:
            playbook_spec = PlaybookSpec.from_yaml(spec_path)
            playbook_specs.append(playbook_spec)
        except Exception as e:
            print(f"Error loading playbook spec {spec_path}: {e}", file=sys.stderr)

    return playbook_specs


def run(
    name: str | None = None,
    path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    playbook_specs = _load_playbook_specs(path)
    if not playbook_specs:
        print("No playbook specs found.", file=sys.stderr)
        raise SystemExit(1)

    if not name:
        playbook_spec = random.choice(playbook_specs)
    else:
        playbook_spec = next((spec for spec in playbook_specs if spec.name == name), None)
        if not playbook_spec:
            print(f"Playbook spec not found: {name}", file=sys.stderr)
            print(
                f"Available: {', '.join(sorted(spec.name for spec in playbook_specs))}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    agent = build_agent(playbook_spec)
    app = agent.to_web()

    print(f"Serving {playbook_spec.name!r} at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    fire.Fire(run)


if __name__ == "__main__":
    main()
