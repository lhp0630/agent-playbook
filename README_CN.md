# agent-playbook

[中文](README_CN.md) | [English](README.md)

agent-playbook 将 YAML Agent Spec 封装为基于 pydantic-ai [`Capability`](https://ai.pydantic.dev/capabilities/) 的智能体：命名 Skill 节点、DynamicWorkflow 编排、可选 MCP 工具，以及用于执行不可信代码的隔离 OpenSandbox。

## 功能

- Spec 驱动的 Agent（`Agent.from_file` with capabilities）。加载了两个及以上 Spec 时，网页对话从路由 Agent 进入
- [`Playbook`](src/harness/playbook)：命名 Skill 节点、DynamicWorkflow 编排、可选 MCP
- [`OpenSandbox`](src/harness/open_sandbox)：隔离容器 workspace，用于执行不可信代码
- 内置 `code-review`，使用 `@zereight/mcp-gitlab` MCP
- 内置 `outlook-mail`，使用 `@softeria/ms-365-mcp-server` MCP

## 安装

Python 3.10+，依赖管理使用 [uv](https://docs.astral.sh/uv/)（已包含 `pydantic-ai-harness[dynamic-workflow]`、`pydantic-ai-skills` 与 `opensandbox`）：

```bash
git clone --recurse-submodules https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups --extra agent
```

`--extra agent` 会安装服务端依赖（`fire`、`uvicorn` 等）。可复用库在 `src/harness/` 的 `harness` 包；CLI/Web 应用在 `src/agent/` 的 `agent` 包。

若已克隆但未拉取子模块：

```bash
git submodule update --init --recursive
```

技能包位于 `.agents/skills/`（`code-review-skill`）。

## 快速开始

复制 `.env.example` 为 `.env`，填入凭证：

```bash
# 省略 playbook `models` 时的模型回退
OPENAI_MODEL=...
OPENAI_BASE_URL=...
OPENAI_API_KEY=...

# 可选 — 启用 GitLab MCP，用于 GitLab 地址
GITLAB_API_URL=https://gitlab.example.com/api/v4
GITLAB_PERSONAL_ACCESS_TOKEN=glpat-xxx

# 可选 — outlook-mail 的 Outlook MCP（绝对路径；一次性执行 `npx -y @softeria/ms-365-mcp-server --login`）
MS365_MCP_TOKEN_CACHE_PATH=/absolute/path/.config/ms365-mcp/.token-cache.json
MS365_MCP_SELECTED_ACCOUNT_PATH=/absolute/path/.config/ms365-mcp/.selected-account.json

# 可选 — OpenSandbox 服务，用于 harness.open_sandbox.OpenSandbox
OPEN_SANDBOX_API_KEY=...
OPEN_SANDBOX_DOMAIN=localhost:8080
```

运行 Playbook：

```bash
agent
```

访问 `http://127.0.0.1:8000`。两个内置 Spec 都加载时，可以要求代码评审，或处理 Outlook 邮件。

## 网页对话

加载了多个 Agent Spec 时，网页对话的唯一入口是路由 Agent。它决定把这一轮转交给某一个 Agent，或向用户追问。路由 capability 按会话保存每个 Agent 的完整 message history。同一会话里来回切换 Agent 时，各自的历史都还在：交给 outlook-mail 的历史不会带上 code-review 的工具记录。路由 Agent 自己的聊天记录仍由 `to_web` 保存，用来判断这一轮是不是在延续上一个 Agent。

只加载了一个 Spec 时，网页对话直接进入该 Agent。

## 编程接入

从 `harness` 导入 Capability（`agent` 包仅作为服务入口）：

```python
from pydantic_ai import Agent

from harness.playbook import Playbook

agent = Agent.from_file(
    '.agents/code-review.yaml',
    custom_capability_types=[Playbook],
)
```

也可在代码中直接构造 Capability：

```python
from pydantic_ai import Agent
from harness.playbook import Playbook

agent = Agent(
    'openai:ornith:35b',
    capabilities=[
        Playbook(
            name='code-review',
            nodes=[],
            mcp_servers=[],
            models={'name': 'openai-chat:ornith:35b', 'model_provider': 'openai'},
            model_providers=[
                {
                    'name': 'openai',
                    'base_url': 'https://api.openai.com/v1',
                    'api_key': '...',
                }
            ],
        )
    ],
)
```

更多说明见 [`src/harness/playbook/README.md`](src/harness/playbook/README.md)。

### OpenSandbox

```python
from pydantic_ai import Agent
from pydantic_ai_harness.filesystem import FileSystem
from pydantic_ai_harness.shell import Shell
from harness.open_sandbox import OpenSandbox

agent = Agent(
    'openai:ornith:35b',
    capabilities=[OpenSandbox(), Shell(), FileSystem()],
)
```

workspace、生命周期与 Agent Spec YAML 见 [`src/harness/open_sandbox/README.md`](src/harness/open_sandbox/README.md)。

## 示例

| Code Review | Outlook Mail |
| --- | --- |
| ![Code Review](readme_assets/img_gitlab.png) | ![Outlook Mail](readme_assets/img_outlook.png) |
