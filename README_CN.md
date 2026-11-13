# agent-playbook

[中文](README_CN.md) | [English](README.md)

基于 [pydantic-ai](https://ai.pydantic.dev/) 的本地通用 Agent harness：
用 YAML 定义专家（MCP + Skills），经 Supervisor 统一进入 Web 对话。

## 运行

前置：Python 3.11+、[uv](https://docs.astral.sh/uv/)。

```bash
git clone --recurse-submodules https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups --extra agent
uv run agent
```

打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。可以要求代码评审，或处理 Outlook 邮件。

若克隆时未拉子模块：`git submodule update --init --recursive`。

| Code Review | Outlook Mail |
| --- | --- |
| ![Code Review](readme_assets/img_gitlab.png) | ![Outlook Mail](readme_assets/img_outlook.png) |

## 你能得到什么

- 本地 Web 对话，做专家向工作（代码评审、邮件等）
- 在 `.agents/` 放一份 YAML 即可增加专家（MCP、Skills、模型写在同一文件）
- 多个专家共用一个聊天入口；Supervisor 转交并隔离历史
- 凭证可选：未设置的 MCP 变量会跳过对应 server，应用仍能启动

## 边界

| 层 | 职责 |
| --- | --- |
| `.agents/*.yaml` | 每个文件一位专家 |
| `src/agent/` | CLI、Web 入口、Supervisor |
| `src/harness/` | MCP / 模型助手 |
| `.agents/skills/` | 技能包 |

不做 Playbook Capability 或 DynamicWorkflow `nodes`——每份 YAML 构建普通 Agent。一个 Spec → 直接对话该 Agent；多个 → Web 唯一入口是 Supervisor。

## 配置（可选）

某专家需要凭证时，再复制 `.env.example` 为 `.env`（模型、GitLab MCP、Outlook MCP）。

```yaml
# .agents/code-review.yaml（示意）
name: code-review
capabilities:
  - WebFetch: { local: true }
  - SkillsCapability:
      directories: [.agents/skills]
      include: [code-review-skill]
```

## 许可证

[MIT](LICENSE)
