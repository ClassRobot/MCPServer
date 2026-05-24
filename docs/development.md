# Development Guide

## 目标
保障 Python MCP Server 具备稳定的扩展结构、清晰的职责划分与良好的可测试性。

## 架构与分层设计

| 层次 | 路径 | 核心职责 | 扩展与新功能规则 |
| :--- | :--- | :--- | :--- |
| **入口层** | `__main__.py` | CLI 参数解析与进程启动，无业务逻辑。 | 保持精简，不放任何具体实现。 |
| **装配层** | `app.py` | 实例化 `FastMCP`，注册各模块能力。 | 仅做能力装配与注册，不写具体业务。 |
| **配置层** | `config.py` | 集中读取环境变量、默认值及配置校验。 | 新增配置项必须在此集中定义。 |
| **能力层** | `tools/`<br>`resources/`<br>`prompts/` | 承载 MCP 的具体能力模块。<br>通过 `__init__.py` 导出统一注册函数。 | 1. 新增独立 Tool/Resource/Prompt 先放入此层。<br>2. 保持各模块高内聚。 |
| **服务层** | `services/` | 跨 Tool 共享的复杂业务流程与编排。 | 多个 Tool 共用相同业务逻辑时，提取至此。 |
| **适配层** | `adapters/` | 外部系统对接（如 Playwright、缓存、Bing）。 | 处理第三方依赖及异常封装，不含业务决策。 |
| **模型层** | `schemas/` | 跨层共享的数据模型与类型定义。 | 避免裸 `dict`，多模块共享的数据结构在此定义。 |

## 开发规范

### 环境与依赖
- **开发环境**: 推荐使用 `uv` 自动管理的 `.venv` 虚拟环境，或任意 Python 3.11+ 运行环境。
- **包管理器**: 项目完全使用 `uv` 管理依赖与环境，保证依赖版本与 `uv.lock` 严格一致。
- **常用命令**:
  ```bash
  uv sync                             # 初始化并同步依赖
  uv run playwright install chromium   # 安装浏览器核心
  uv run ruff check .                 # 代码静态检查与 Lint
  uv run ruff format .                # 代码格式化
  uv run pytest                       # 运行单元测试
  ```

### 测试约定
- 测试目录 `tests/` 结构与 `src/` 的职责映射保持一致。
- 优先对纯逻辑和工具做单元测试；确保 CLI 启动与配置解析具备最小覆盖，防止变更隐式出错。

### 日志约定
- 日志配置默认读取 `config/logging.yaml`，可通过 `MCP_LOGGING_CONFIG_PATH` 指定其他 YAML。
- 默认同时输出到终端 `stderr` 和本地文件 `runtime/logs/mcp-server.log`。
- 终端日志默认启用 ANSI 彩色输出，文件日志始终保持纯文本，避免回溯和 grep 时混入转义字符。
- 本地日志按天滚动，默认保留 14 天。
- 常用调试变量：`MCP_LOG_LEVEL=DEBUG`、`MCP_LOG_CONSOLE_COLOR=false`、`MCP_LOG_TOOL_ARGS=true`。
- Tool 参数日志默认关闭；开启后也只记录安全摘要，敏感字段会脱敏，长文本会截断。

### 变更原则
1. **就近与下沉**: 仅单一模块使用的帮助函数保持就近；业务变复杂或多模块共享时，再下沉至 `services/` 或 `adapters/`。
2. **单一职责**: Tool/Resource 仅处理参数边界和输入输出，复杂编排下沉。
3. **闭环变更**: 引入新目录或新功能模块时，需在同一次变更中补齐对应目录的 `README.md`。每次结构调整后须确保 Lint 和测试全部通过。
