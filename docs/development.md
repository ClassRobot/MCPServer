# Development Guide

## 目标

这个项目用于持续开发 Python MCP Server，不只追求“能跑”，还要保证后续新增工具、资源、提示词时结构稳定、职责清晰、便于测试。

## 分层约定

### 入口层

- `src/mcp_server/__main__.py`
- 负责 CLI 参数解析和进程启动。
- 不承载具体业务逻辑。

### 应用装配层

- `src/mcp_server/app.py`
- 负责创建 `FastMCP` 实例并注册 tools、resources、prompts。
- 这里只做装配，不写具体能力实现。

### 配置层

- `src/mcp_server/config.py`
- 负责环境变量读取、默认值、配置校验。
- 新增配置时，优先在这里集中定义。

### 能力层

- `src/mcp_server/tools/`
- `src/mcp_server/resources/`
- `src/mcp_server/prompts/`
- 每个模块只负责一类能力，并提供统一的注册函数。

### 扩展层

当项目开始接真实业务时，按需要补以下目录：

- `src/mcp_server/services/`: 业务流程、外部 API 调用、数据库访问
- `src/mcp_server/schemas/`: 输入输出模型、共享数据结构
- `src/mcp_server/adapters/`: 第三方系统适配器

## 新功能放置规则

1. 如果只是新增一个独立 MCP tool，先放进 `tools/`。
2. 如果多个 tool 共用相同业务逻辑，把重复逻辑提取到 `services/`。
3. 如果多个模块共享稳定数据结构，用显式类型而不是裸 `dict`。
4. 如果只被一个模块使用的帮助函数，不要过早上提到全局共享目录。

## 测试约定

- `tests/` 中的测试应镜像 `src/` 的职责边界。
- Tool 的纯逻辑优先做单元测试。
- 配置解析和 CLI 参数解析要有最小覆盖，避免后续运行方式变更时静默出错。

## 环境约定

- 开发环境统一使用 conda 环境 `classbot-mcp`。
- 使用 [environment.yml](../environment.yml) 创建环境。
- 在 PowerShell 中，激活 conda 后还需要将 `VIRTUAL_ENV` 指向 `$env:CONDA_PREFIX`，这样 `uv --active` 才会把 conda 环境当作目标环境。
- 依赖安装和更新使用 `uv sync --active`。
- 项目命令执行默认使用 `uv run --active ...`。
- 不在仓库目录内创建 `.venv` 作为项目默认环境。

## 目录文档约定

- 每个承担开发职责的目录都应放置自己的 `README.md`。
- 目录 README 的目标是帮助开发者理解“这里为什么存在、应该放什么、如何扩展”。
- 不要求所有目录使用同一模板。
- `tools/`、`resources/`、`prompts/`、`tests/`、`docs/` 这类目录应根据自身用途采用不同写法。
- 新增 `services/`、`schemas/`、`adapters/` 等新目录时，应在同一变更中补上对应 README。

## 开发命令

```powershell
conda activate classbot-mcp
$env:VIRTUAL_ENV = $env:CONDA_PREFIX
uv sync --active
uv run --active ruff check .
uv run --active ruff format .
uv run --active pytest
```

## 变更原则

1. 新增结构前先确认是否已经有合适的落点。
2. Tool 只处理参数边界和结果返回，不负责复杂业务编排。
3. 配置读取保持集中，避免隐式依赖当前工作目录或源码相对路径。
4. 每次结构调整后都运行 lint 和 tests。
