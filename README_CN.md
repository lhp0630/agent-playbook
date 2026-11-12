# agent-playbook

[中文](README_CN.md) | [English](README.md)

基于 YAML **PlaybookSpec** 的智能体（扩展 pydantic-ai [`AgentSpec`](https://ai.pydantic.dev/)），含 MCP、Skills，以及 Web 端 **Supervisor**。

## 架构

| 层 | 职责 |
| --- | --- |
| `.agents/*.yaml` | 每个文件一份 [`PlaybookSpec`](src/agent/playbook_spec.py)：在 AgentSpec 字段之上增加顶层 `mcp_servers` / `models` / `model_providers` |
| `capabilities` | 标准 pydantic-ai 能力（`WebFetch`、[`SkillsCapability`](https://github.com/pydantic/pydantic-ai-skills)、可选 [`Model`](src/harness/models/README.md) 等） |
| [`harness.mcp`](src/harness/mcp/README.md) | 对齐 Claude 的 MCP 条目 → 带前缀 toolset；必填 `${VAR}` 未设置时跳过该 server |
| [`harness.models`](src/harness/models/README.md) | 多 provider 解析，以及可选的 Model capability |
| [`Supervisor`](src/agent/supervisor.py) | 加载多个 Spec 时的唯一 Web 入口：handoff 工具 + 按会话隔离的各 Agent 历史 |

不再有 Playbook Capability，也不再有 DynamicWorkflow 的 `nodes` 编排——专业 Agent 由 `PlaybookSpec.to_agent()` 直接构建。

## 功能

- 多 Spec 时经 Supervisor 进入；单 Spec 时直接对话该 Agent
- 每个 PlaybookSpec 顶层配置 MCP 与可选模型菜单
- Skills 等走 Agent 的 `capabilities` 列表
- 仅写 name 的模型条目走 pydantic-ai `infer_model`（如 `OPENAI_API_KEY`）；自定义端点用 `model_providers`

## 安装

Python 3.11+，依赖管理使用 [uv](https://docs.astral.sh/uv/)（已包含 `pydantic-ai-skills`）：

```bash
git clone --recurse-submodules https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups --extra agent
```

`--extra agent` 会安装服务端依赖（`fire`、`uvicorn`、`pyyaml` 等）。可复用助手在 `src/harness/`；CLI/Web 应用在 `src/agent/`。

若已克隆但未拉取子模块：

```bash
git submodule update --init --recursive
```

技能包位于 `.agents/skills/`（`code-review-skill`）。

## 快速开始

复制 `.env.example` 为 `.env`，填入凭证：

```bash
# 可选 — 仅 name 的模型走原生 infer_model（openai:/anthropic:/google:…）
# OPENAI_API_KEY=...
# ANTHROPIC_API_KEY=...

# 可选 — GitLab MCP（未设置时构建 Agent 会跳过该 server；GitHub 评审仍可用）
GITLAB_API_URL=https://gitlab.example.com/api/v4
GITLAB_PERSONAL_ACCESS_TOKEN=glpat-xxx

# 可选 — outlook-mail 的 Outlook MCP（绝对路径；一次性执行 `npx -y @softeria/ms-365-mcp-server --login`）
MS365_MCP_TOKEN_CACHE_PATH=/absolute/path/.config/ms365-mcp/.token-cache.json
MS365_MCP_SELECTED_ACCOUNT_PATH=/absolute/path/.config/ms365-mcp/.selected-account.json
```

启动服务：

```bash
agent
```

访问 `http://127.0.0.1:8000`。两个内置 PlaybookSpec 都加载时，可以要求代码评审，或处理 Outlook 邮件。

## 网页对话

加载了多个 PlaybookSpec 时，网页对话的唯一入口是 Supervisor Agent。它把这一轮交给某一个专业 Agent，或向用户追问。Supervisor capability 按会话保存每个专业 Agent 的完整 message history，因此交给 outlook-mail 的历史不会带上 code-review 的工具记录。Supervisor 自己的聊天记录仍由 `to_web` 保存，用来判断这一轮是否在延续上一个专业 Agent。

只加载了一个 PlaybookSpec 时，网页对话直接进入该 Agent。

## 编程接入

```python
from agent import PlaybookSpec
from agent.supervisor import CUSTOM_CAPABILITY_TYPES

spec = PlaybookSpec.from_file('.agents/code-review.yaml')
agent = spec.to_agent(custom_capability_types=CUSTOM_CAPABILITY_TYPES)
```

- [`PlaybookSpec`](src/agent/playbook_spec.py) — AgentSpec + `mcp_servers` / `models` / `model_providers`
- [`Model`](src/harness/models/README.md) — 可选 Model capability 与多 provider 解析
- [`harness.mcp`](src/harness/mcp/README.md) — 对齐 Claude 的 MCP toolset 构建（环境变量前置校验并跳过）

## 示例

| Code Review | Outlook Mail |
| --- | --- |
| ![Code Review](readme_assets/img_gitlab.png) | ![Outlook Mail](readme_assets/img_outlook.png) |
