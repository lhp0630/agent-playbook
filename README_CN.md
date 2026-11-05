# agent-playbook

[中文](README_CN.md) | [English](README.md)

由 YAML 格式 Agent Spec 驱动的智能体。

## 功能

- 加载多个 Playbook Spec 时，经 supervisor 智能体进入
- 支持配置 Workflow，编排多节点智能体
- 支持配置 MCP 工具

## 安装

Python 3.11+，依赖管理使用 [uv](https://docs.astral.sh/uv/)（已包含 `pydantic-ai-harness` 与 `pydantic-ai-skills`）：

```bash
git clone --recurse-submodules https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups --extra agent
```

`--extra agent` 会安装服务端依赖（`fire`、`uvicorn`、`pyyaml` 等）。可复用库在 `src/harness/` 的 `harness` 包；CLI/Web 应用在 `src/agent/` 的 `agent` 包。

若已克隆但未拉取子模块：

```bash
git submodule update --init --recursive
```

技能包位于 `.agents/skills/`（`code-review-skill`）。

## 快速开始

复制 `.env.example` 为 `.env`，填入凭证：

```bash
# 可选 — 仅 name 的 Model 条目走 infer_model 时需要的厂商环境变量（anthropic:/google:/openai-chat:）
# OPENAI_API_KEY=...
# ANTHROPIC_API_KEY=...

# 可选 — 启用 GitLab MCP，用于 GitLab 地址
GITLAB_API_URL=https://gitlab.example.com/api/v4
GITLAB_PERSONAL_ACCESS_TOKEN=glpat-xxx

# 可选 — outlook-mail 的 Outlook MCP（绝对路径；一次性执行 `npx -y @softeria/ms-365-mcp-server --login`）
MS365_MCP_TOKEN_CACHE_PATH=/absolute/path/.config/ms365-mcp/.token-cache.json
MS365_MCP_SELECTED_ACCOUNT_PATH=/absolute/path/.config/ms365-mcp/.selected-account.json
```

运行 Playbook：

```bash
agent
```

访问 `http://127.0.0.1:8000`。两个内置 Spec 都加载时，可以要求代码评审，或处理 Outlook 邮件。

## 网页对话

加载了多个 Agent Spec 时，网页对话的唯一入口是 supervisor Agent。它决定把这一轮转交给某一个 Agent，或向用户追问。supervisor capability 按会话保存每个 Agent 的完整 message history。同一会话里来回切换 Agent 时，各自的历史都还在：交给 outlook-mail 的历史不会带上 code-review 的工具记录。supervisor Agent 自己的聊天记录仍由 `to_web` 保存，用来判断这一轮是不是在延续上一个 Agent。

只加载了一个 Spec 时，网页对话直接进入该 Agent。

## 编程接入

从 `harness` 导入 Capability（`agent` 包仅作为服务入口）：

```python
from pydantic_ai import Agent

from harness.models import Model
from harness.playbook import Playbook

agent = Agent.from_file(
    '.agents/code-review.yaml',
    custom_capability_types=[Playbook, Model],
)
```

- [`Model`](src/harness/models/README.md) — provider 菜单与模型解析
- [`Playbook`](src/harness/playbook/README.md) — nodes / skills / MCP（DynamicWorkflow）

## 示例

| Code Review | Outlook Mail |
| --- | --- |
| ![Code Review](readme_assets/img_gitlab.png) | ![Outlook Mail](readme_assets/img_outlook.png) |
