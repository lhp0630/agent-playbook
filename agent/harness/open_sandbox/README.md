# OpenSandbox

`OpenSandbox` gives an agent an isolated container for running commands and working
with files. Use it for coding, data processing, and other tasks that should not
execute model-generated commands on the application host.

The capability adds shell and file tools backed by
[OpenSandbox](https://github.com/opensandbox-group/OpenSandbox) via the same
`opensandbox` SDK used by
[`OpenSandboxScriptExecutor`][pydantic_ai_skills.sandboxes.opensandbox.OpenSandboxScriptExecutor].
By default, every agent run gets a fresh sandbox created from a container image.
The capability destroys it when the run ends. You can also attach an existing
sandbox or reuse one across several runs.

> [!NOTE]
> Import from the submodule -- there is no top-level re-export:
>
> ```python
> from agent.harness.open_sandbox import OpenSandbox
> ```

## Quick start

Install the `opensandbox` extra (already included when using
`pydantic-ai-skills[opensandbox]`) and point at a reachable OpenSandbox server:

```bash
uv add "pydantic-ai-skills[opensandbox]"
export OPEN_SANDBOX_API_KEY=...
export OPEN_SANDBOX_DOMAIN=localhost:8080   # optional; defaults to localhost:8080
```

Add `OpenSandbox` to the agent:

```python
from pydantic_ai import Agent
from agent.harness.open_sandbox import OpenSandbox

agent = Agent(
    'openai:Qwen3.8-27b',
    capabilities=[OpenSandbox()],
)

result = agent.run_sync('Create a Python script and run its tests.')
print(result.output)
```

## Tools

| Tool | Purpose |
|---|---|
| `run_command` | Run a shell command (`sh -c`) in the sandbox. |
| `read_file` | Read a text file from the sandbox. |
| `write_file` | Write text to a file (creating parent directories). |
| `list_directory` | List a directory's entries (directories shown with a trailing `/`). |

Output is labelled with `[stdout]` / `[stderr]` markers and an `[exit code: N]`
line on non-zero exit. Streams and file reads are truncated by `max_output_bytes`
and `max_output_lines`. A non-zero exit from `run_command` is reported, not raised.

## Sandbox lifetime

- **Owned** (default): each run creates a fresh sandbox and destroys it on exit.
- **Attach** (`sandbox_id=...`): connect to an existing sandbox; never destroy it.
- **Injected session** (`session=...`): reuse a caller-owned `OpenSandboxSession`;
  the capability never opens or closes it.

Owned-only settings (`image`, `sandbox_timeout`, `workdir`, `env`) cannot be
combined with `sandbox_id` or `session`.

## Failure handling

- **Recoverable** (`OpenSandboxError`) → `ModelRetry` so the model can react.
- **Terminal** (`OpenSandboxUnavailableError`, `OpenSandboxAuthError`) → propagate
  and end the run.

## Agent-spec YAML

```yaml
capabilities:
  - OpenSandbox:
      image: opensandbox/code-interpreter:v1.1.0
      sandbox_timeout: 300
```

```python
from pydantic_ai import Agent
from agent.harness.open_sandbox import OpenSandbox

agent = Agent.from_file(
    'agent.yaml',
    custom_capability_types=[OpenSandbox],
)
```
