# Badger

[中文](README.md) | [English](README_EN.md)

由 YAML 配置去驱动多角色以及多阶段的 AI 讨论模拟器。例如配置具有鲜明个性的 AI 角色开启一场辩论。又或者进行项目需求评审，或代码审核。

## 功能

- 基于 LangChain 的 YAML 配置驱动引擎
- 支持多阶段、多角色协作讨论流程
- 内置取名、辩论、需求评审、代码评审流程
- 每个角色可单独配置不同的 LLM 模型
- 支持 `.env` 环境变量和 YAML 配置文件
- Topic 支持三种模式：动态生成、硬编码、外部文件引用

## 安装

需要 Python 3.10+，使用 [uv](https://docs.astral.sh/uv/) 管理依赖：

```bash
git clone https://github.com/lhp0630/debate.git && cd debate
uv sync
```

## 运行

复制 `.env.example` 为 `.env`，填入模型信息：

```bash
OPENAI_MODEL=your-model-name
OPENAI_BASE_URL=https://your-api-endpoint/v1
OPENAI_API_KEY=sk-xxx
```

环境变量作为最低优先级的 fallback，yaml 中配置了则不使用环境变量。

```bash
uv run badger                                          # 默认取名流程
uv run badger --config badger/config/naming.yaml       # 指定取名流程
uv run badger --config badger/config/debate.yaml       # 辩论流程
uv run badger --config badger/config/requirement_review.yaml  # 需求评审
uv run badger --config badger/config/code_review.yaml         # 代码评审
```

## 配置

配置文件位于 `badger/config/` 目录：

- `naming.yaml` - 取名流程（默认）
- `debate.yaml` - 辩论流程
- `requirement_review.yaml` - 需求评审流程
- `code_review.yaml` - 代码评审流程

配置结构：

```yaml
llm:                          # 全局模型配置（fallback）
  # model: "gpt-4o-mini"
  # base_url: ""
  # api_key: ""

temperature: 0.8
topic: "需求描述"              # 可选：硬编码 topic 或 "file:path/to/file.md"

instructions: |               # 可选：全局系统提示词
  IMPORTANT: Always respond in Chinese.

roles:                        # 角色定义
  - name: "Zhang Wei"
    description: |            # 角色描述（自动注入到 system_prompt）
      Architect. Rigorous, deep thinker.
      Expertise in Python system architecture.
    llm:
      # model: "gpt-4o"

flow:                         # 流程定义
  name: "流程名称"
  description: "流程描述"
  stages:                     # 阶段列表
    - name: "阶段1"
      description: "阶段描述"
      steps:                  # 步骤列表
        - role: "角色名"
          system_prompt: |
            You are {role_name}.
            {role_description}
            ...你的提示词...
          input: |
            用户输入: {user_input}
            上下文: {context}
```

## Topic 模式

1. **动态生成**：`topic` 为空，由流程步骤生成（如辩论流程）
2. **硬编码**：`topic: "需求描述"`
3. **外部文件**：`topic: "file:code_review_example.md"`（相对路径基于配置文件目录）

## 自定义流程

1. 在 `badger/config/` 目录创建新的 YAML 配置文件
2. 定义 `roles`（角色）和 `flow`（流程）
3. 使用 `--config` 参数运行

## License

[MIT](LICENSE)
