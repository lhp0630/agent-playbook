# Badger

[中文](README_CN.md) | [English](README.md)

Badger 是一个**声明式多智能体分治 Agent 框架**。复杂任务被拆解为专业角色与顺序阶段，全部在 YAML 中定义 — 无需硬编码编排图。每个 YAML 文件定义一个 Agent；换一份配置即可定义新的领域 Agent。

## 功能

- YAML 配置驱动，基于 LangChain
- 多 Agent 分阶段协作（`roles` + `stages` + `steps`）
- 可插拔执行计划、步骤执行器与生命周期钩子
- 内置取名、辩论、需求评审、代码评审 Agent

## 安装

Python 3.10+，依赖管理使用 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/lhp0630/badger.git && cd badger
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
uv run badger -n "name generation"
uv run badger -n "office debate"
uv run badger -n "requirement review"
uv run badger -n "code review"
```

加载自定义 Agent 配置目录：

```bash
uv run badger -n "my flow" -p ./my_flows
```

## 示例

代码评审 Agent 读取 `code_review.yaml` 中的示例代码，多角色协作输出问题分析与修复建议：

```bash
uv run badger -n "code review"
```

<!-- ![Code Review](./readme_assets/code_review.gif) -->

## 内置 Agent

配置文件位于 `agent/builtin_agents/`：

| 文件 | Agent 名 |
|------|--------|
| `naming.yaml` | Name Generation |
| `debate.yaml` | Office Debate |
| `requirement_review.yaml` | Requirement Review |
| `code_review.yaml` | Code Review |

## 自定义 Agent

编写 YAML 配置文件，通过 `-p` 指定目录、`-n` 按名称运行。配置结构与模板变量详见 [docs/technical.md](docs/technical.md)，架构说明见 [docs/architecture.md](docs/architecture.md)。

## License

[MIT](LICENSE)
