"""OpenSandbox capability: gives an agent run an isolated container workspace.

``OpenSandbox`` is the supported entry point. Compose it with tools that use
``ctx.workspace``, such as ``Shell`` and ``FileSystem``.
``OpenSandboxBackend`` is the OpenSandbox implementation of Pydantic AI's workspace
backend protocols, for applications that create or attach to a sandbox themselves
and pass it to a run as ``workspace=``.
"""

from harness.open_sandbox._backend import OpenSandboxBackend
from harness.open_sandbox._capability import OpenSandbox

__all__ = [
    "OpenSandbox",
    "OpenSandboxBackend",
]
