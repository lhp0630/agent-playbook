# OpenSandbox

`OpenSandbox` gives an agent run an isolated container workspace. Commands and file
operations run inside that container, not on the application host.

The capability supplies the workspace only. Compose it with
[`Shell`](https://pydantic.dev/docs/ai/harness/shell/) and
[`FileSystem`](https://pydantic.dev/docs/ai/harness/filesystem/), or call
`ctx.workspace` from your own tools. File operations use the sandbox
`files` service (`Sandbox.files`); commands use `Sandbox.commands`.

The backend talks to [OpenSandbox](https://github.com/opensandbox-group/OpenSandbox)
through the `opensandbox` SDK directly. A fresh sandbox is created the first time
the run uses the workspace, and it is not deleted when the run ends. Delete it with
`OpenSandbox.destroy` and the run's `workspace.ref`.

> [!NOTE]
> Import from the `harness` package:
>
> ```python
> from harness.open_sandbox import OpenSandbox
> ```

## Quick start

```bash
uv add opensandbox
export OPEN_SANDBOX_API_KEY=...
export OPEN_SANDBOX_DOMAIN=localhost:8080   # optional; defaults to localhost:8080
```

```python
from pydantic_ai import Agent
from pydantic_ai_harness.filesystem import FileSystem
from pydantic_ai_harness.shell import Shell
from harness.open_sandbox import OpenSandbox

agent = Agent(
    'openai:ornith:35b',
    capabilities=[OpenSandbox(image='opensandbox/code-interpreter:v1.1.0'), Shell(), FileSystem()],
)

result = agent.run_sync('Create a Python script and run its tests.')
print(result.output)
```

A custom tool uses the same workspace:

```python
from pydantic_ai import Agent, RunContext

@agent.tool
async def run_python(ctx: RunContext, code: str) -> str:
    """Run a Python snippet in the sandbox."""
    result = await ctx.workspace.run(['python', '-c', code], timeout=10)
    return result.stdout + result.stderr
```

## Sandbox lifetime

- **Created** (default): the first workspace operation creates a sandbox from `image`.
  The backend does not destroy it when the run ends.
- **Continue**: the next run finds `WorkspaceRef(provider='opensandbox', id=...)` on
  the message history, or you pass that ref as `workspace=`.
- **Fresh**: pass `workspace='new'` to ignore the ref recorded in history.
- **Already running**: build `OpenSandboxBackend(sandbox=sandbox)` and pass it as
  `workspace=`. The capability's `image` and `sandbox_timeout` do not apply to it.

```python
ref = result.workspace.ref
await OpenSandbox().destroy(ref)
```

`image` and `sandbox_timeout` apply only when creating a sandbox. `working_dir` and
`env` apply to every command, including on an attached sandbox.

## Agent-spec YAML

```yaml
capabilities:
  - OpenSandbox:
      image: opensandbox/code-interpreter:v1.1.0
      sandbox_timeout: 300
  - Shell: {}
  - FileSystem: {}
```

```python
from pydantic_ai import Agent
from harness.open_sandbox import OpenSandbox

agent = Agent.from_file(
    'agent.yaml',
    custom_capability_types=[OpenSandbox],
)
```
