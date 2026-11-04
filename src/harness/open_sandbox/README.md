# OpenSandbox

Run the agent's commands and file edits in an isolated
[OpenSandbox](https://github.com/opensandbox-group/OpenSandbox) container, created on
first use. The capability supplies the workspace only: compose it with
[`Shell`](https://pydantic.dev/docs/ai/harness/shell/) and
[`FileSystem`](https://pydantic.dev/docs/ai/harness/filesystem/), or call
`ctx.workspace` from your own tools.

[Source](./)

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
```

A fresh sandbox is created the first time the run uses the workspace and is not deleted
when the run ends. A follow-up with the same message history reattaches; pass
`workspace='new'` for a fresh one, or store `result.workspace.ref` and pass it as
`workspace=` later. Destroy it with `OpenSandbox.destroy(ref)`.

`image`, `sandbox_timeout`, and `volumes` shape only a newly created sandbox;
`working_dir` and `env` apply to every command, including an attached one.

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

agent = Agent.from_file('agent.yaml', custom_capability_types=[OpenSandbox])
```

See [Workspaces](https://pydantic.dev/docs/ai/core-concepts/workspace/) for refs,
`workspace='new'`, and composing other workspace capabilities.
