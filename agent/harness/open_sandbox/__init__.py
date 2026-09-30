"""OpenSandbox capability: gives agents an isolated container sandbox to work in.

`OpenSandbox` is the supported entry point; build an agent with it and use its tools.
`OpenSandboxSession` exposes lower-level lifecycle, command, and file access for
applications that need to share a caller-owned sandbox across runs. The model-facing
toolset remains an implementation detail of the capability.
"""

from agent.harness.open_sandbox._capability import OpenSandbox
from agent.harness.open_sandbox._session import (
    OpenSandboxAuthError,
    OpenSandboxError,
    OpenSandboxExecResult,
    OpenSandboxSession,
    OpenSandboxTerminalError,
    OpenSandboxUnavailableError,
)

__all__ = [
    "OpenSandbox",
    "OpenSandboxAuthError",
    "OpenSandboxError",
    "OpenSandboxExecResult",
    "OpenSandboxSession",
    "OpenSandboxTerminalError",
    "OpenSandboxUnavailableError",
]
