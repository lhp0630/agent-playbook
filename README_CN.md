# agent-playbook

[中文](README_CN.md) | [English](README.md)

agent-playbook 是基于 pydantic-ai DynamicWorkflow 的 YAML 多智能体工作流。

## 功能

- YAML 配置驱动，基于 [pydantic-ai](https://ai.pydantic.dev/) + [pydantic-ai-harness](https://github.com/pydantic/pydantic-ai-harness) `DynamicWorkflow`
- `cast` 成为子 Agent（从配置读取 `name`、`description`、`model`）
- 内置取名、辩论、需求评审、代码评审 Agent
- 通过 `agent.to_web()` 提供 Web 聊天界面（uvicorn）

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

运行内置 Playbook（`-n` 须与 YAML 中的 `name` **完全一致**；省略则随机选择）。会启动 Web 聊天界面，在浏览器中输入需求即可：

```bash
agent -n "Name Generation"
agent -n "Office Debate"
agent -n "Requirement Review"
agent -n "Code Review"
```

可选监听地址（默认 `127.0.0.1:8000`）：

```bash
agent -n "Code Review" --host 127.0.0.1 --port 8000
```

加载自定义 Playbook 配置目录：

```bash
agent -n "My Playbook" -p ./my_playbooks
```

## 示例

取名 Agent 的 Web UI：编排器规划多角色工作流，并返回最终结果：

```bash
agent -n "Name Generation"
```

| | |
| --- | --- |
| ![Web UI — workflow planning](./readme_assets/web_1.png) | ![Web UI — final result](./readme_assets/web_2.png) |

## License

[MIT](LICENSE)
