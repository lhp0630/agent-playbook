# agent-playbook

[中文](README_CN.md) | [English](README.md)

agent-playbook 是基于 pydantic-ai DynamicWorkflow 的 YAML 多智能体工作流。

## 功能

- YAML 配置驱动，基于 [pydantic-ai](https://ai.pydantic.dev/) + [pydantic-ai-harness](https://github.com/pydantic/pydantic-ai-harness) `DynamicWorkflow`
- `roles` 成为子 Agent（从配置读取 `name`、`description`、`model`）
- 内置取名、辩论、需求评审、代码评审 Agent

## 安装

Python 3.10+，依赖管理使用 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/lhp0630/agent-playbook.git && cd agent-playbook
uv sync --all-groups
```

## 快速开始

复制 `.env.example` 为 `.env`，填入模型信息：

```bash
OPENAI_MODEL=your-model-name
OPENAI_BASE_URL=https://your-api-endpoint/v1
OPENAI_API_KEY=sk-xxx
```

运行内置 Agent（`-n` 指定 Agent 名，省略则随机选择）：

```bash
agent -n "name generation"
agent -n "office debate"
agent -n "requirement review"
agent -n "code review"
```

加载自定义 Agent 配置目录：

```bash
agent -n "my flow" -p ./my_flows
```

## 示例

代码评审 Agent 读取 `code_review.yaml` 中的示例代码，多角色协作输出问题分析与修复建议：

```bash
agent -n "code review"
```

## 内置 Agent

配置文件位于 `agent/builtin_agents/`：

| 文件 | Agent 名 |
|------|--------|
| `naming.yaml` | Name Generation |
| `debate.yaml` | Office Debate |
| `requirement_review.yaml` | Requirement Review |
| `code_review.yaml` | Code Review |

每个 YAML 提供编排器的 `name` / `description` / `llm.model`，以及成为 DynamicWorkflow 子 Agent 的 `roles`。

## 自定义 Agent

编写包含 `name`、`description`、`llm`、`roles` 的 YAML，通过 `-p` 指定目录、`-n` 按名称运行。可选的 `stages` 会作为编排器的建议工作流提示。

## License

[MIT](LICENSE)
