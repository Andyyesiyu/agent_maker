Agent Maker（通用 LLM Agent 构建器）

一个在本文件夹中即可使用的“Agent 祖先”，帮助你快速、规范地构建符合最佳实践的 Agent：
- 工具使用（tool use）
- 规划（planning）与 TODO 管理
- 可观测与可控（step 限制、日志追踪）
- 模板化脚手架（scaffold）一键生成 Agent 项目

无需额外依赖（仅使用标准库），如需接入实际模型，可配置对应 Provider（如 OpenAI），否则会降级为本地 DummyProvider（用于演示与离线开发）。

## 快速开始（使用 uv 管理环境）

推荐使用 uv 管理 Python 与依赖，无需手动创建虚拟环境：

- 安装 uv（任选其一）：
  - macOS/Homebrew：`brew install uv`
  - 官方脚本：`curl -LsSf https://astral.sh/uv/install.sh | sh`

- 创建与进入虚拟环境（可选）：
  - `uv venv`（将在本仓库创建 `.venv`）
  - 激活：`source .venv/bin/activate`（Windows: `./.venv/Scripts/activate`）

- 直接运行（无需激活环境，uv 会使用本地环境）：
  - 列出内置工具：`uv run python -m agent_maker.cli list-tools`
  - 最小内置 Agent 运行：`uv run python -m agent_maker.cli run --task "创建 TODO 并写入 demo.txt"`

- 生成/更新锁文件（可选，推荐提交）：
  - `uv lock`

- 可选依赖（OpenAI）：
  - 安装：`uv add openai`
  - 运行设计器：`uv run python -m agent_maker.cli design --prompt "……" --provider openai`

### 旧方式（不使用 uv，仅标准 Python）

- 列出内置工具：`PYTHONPATH=. python -m agent_maker.cli list-tools`
- 直接创建新 Agent：`PYTHONPATH=. python -m agent_maker.cli new my_agent --desc "一个示例 Agent" --tools todo,fs`
- 运行生成的 Agent：`PYTHONPATH=. python agents/my_agent/main.py --task "帮我创建一个 TODO 并写入文件"`

- 通过“设计 + 脚手架”两步（使用 uv）：
  - 设计：`uv run python -m agent_maker.cli design --prompt "做一个能读写文件并管理待办的 Agent" --out spec.json`
  - 脚手架：`uv run python -m agent_maker.cli scaffold --spec spec.json --dest agents/auto_agent`

## 接入真实 LLM Provider（可选）

- OpenAI（如需）：
  - 安装依赖：`uv add openai`
  - 环境变量：`OPENAI_API_KEY`、`OPENAI_BASE_URL`（可选）、`OPENAI_MODEL`（默认 `gpt-4o-mini`）
  - 命令：`uv run python -m agent_maker.cli design --prompt "……" --provider openai`
  - 若本地未安装 `openai` 包，CLI 会提示安装。

## 设计理念与最佳实践

- 统一工具协议：Tool 使用 JSON-Schema 描述参数；调用统一经过安全网关（可限制文件系统、Shell 等）。
- 规划 + TODO：内置 PlanManager + Todo 工具；Agent 可在对话中显式维护计划与任务清单。
- Agent 循环："思考-规划-行动-反思"，提供 `max_steps`、观察日志（JSONL trace）。
- 模板化工程：`new/scaffold` 会生成最小可运行工程，默认依赖本仓库核心库（无需安装第三方）。

## 目录结构

- `agent_maker/`：核心库与 CLI
- `agents/`：通过脚手架生成的 Agent 工程（默认输出位置）
- 运行追踪：`runs/<run_id>/trace.jsonl`

## 许可证

本项目示例代码供内部开发演示使用，未附带许可证。若需开源/发布，请根据你的需要添加相应 LICENSE。
