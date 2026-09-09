from pathlib import Path

from agent import PlaybookSpec, __version__


def test_package_version() -> None:
    assert __version__


def test_load_codereview_playbook() -> None:
    path = Path(".agents") / "code-review.yaml"
    spec = PlaybookSpec.from_yaml(path)
    assert spec.name == "code-review"
    assert spec.nodes
    assert spec.mcp_servers
    assert any(server.name == "gitlab" for server in spec.mcp_servers)
