# MCP Server

基于 Python、`conda` 和 `uv` 的 MCP Server 项目骨架，默认使用官方 `FastMCP` SDK。

## 快速开始

```powershell
conda env create -f environment.yml
conda activate classbot-mcp
$env:VIRTUAL_ENV = $env:CONDA_PREFIX
uv sync --active
uv run --active playwright install chromium
uv run --active mcp-server
```

默认通过 `stdio` 启动，适合接入 Claude Desktop、Cherry Studio 或其他 MCP Client。

这个项目约定使用固定的 conda 环境 `classbot-mcp` 开发，不在项目目录内创建 `.venv`。
由于 `uv --active` 依赖 `VIRTUAL_ENV`，在 PowerShell 下使用 conda 时需要显式执行：

```powershell
$env:VIRTUAL_ENV = $env:CONDA_PREFIX
```

如果你想用 Streamable HTTP 方式启动：

```powershell
conda activate classbot-mcp
$env:VIRTUAL_ENV = $env:CONDA_PREFIX
uv run --active mcp-server --transport streamable-http
```

如果你要指定监听地址和端口：

```powershell
conda activate classbot-mcp
$env:VIRTUAL_ENV = $env:CONDA_PREFIX
uv run --active mcp-server --transport streamable-http --host 0.0.0.0 --port 8000
```

## 常用命令

```powershell
conda activate classbot-mcp
$env:VIRTUAL_ENV = $env:CONDA_PREFIX
uv sync --active
uv run --active pytest
uv run --active ruff check .
uv run --active ruff format .
```

## 环境变量

项目支持通过环境变量覆盖服务元数据和 HTTP 运行参数：

```bash
MCP_SERVER_NAME
MCP_SERVER_INSTRUCTIONS
MCP_SERVER_HOST
MCP_SERVER_PORT
MCP_SERVER_MOUNT_PATH
MCP_SERVER_STREAMABLE_HTTP_PATH
```

另外，开发时 `uv --active` 还依赖：

```powershell
VIRTUAL_ENV=$env:CONDA_PREFIX
```

## 项目结构

```text
.
├── docs/
│   └── development.md
├── config/
│   └── browser_search.yaml
├── environment.yml
├── pyproject.toml
├── README.md
├── src/
│   └── mcp_server/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── adapters/
│       ├── config.py
│       ├── schemas/
│       ├── server.py
│       ├── services/
│       ├── prompts/
│       ├── resources/
│       └── tools/
└── tests/
    ├── fixtures/
    ├── test_bing_provider.py
    ├── test_browser_config.py
    ├── test_browser_service.py
    ├── test_browser_session.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_search_cache.py
    ├── test_search_results.py
    └── test_server.py
```

## 开发组织约定

1. 新增 `tool` 时，优先放到 `src/mcp_server/tools/`，按领域拆文件，而不是继续堆在入口里。
2. 新增 `resource` 和 `prompt` 时，分别放到 `src/mcp_server/resources/` 与 `src/mcp_server/prompts/`。
3. 共享配置统一放在 `src/mcp_server/config.py`，不要把环境变量读取散落到各模块。
4. 业务逻辑如果开始变复杂，优先新增 `services/`、`schemas/`、`adapters/` 等包，再让 tool 只负责参数边界和结果返回。
5. 开发环境统一使用 conda 环境 `classbot-mcp`，依赖同步和命令执行默认带 `--active`，不要在仓库里新建 `.venv`。
6. 每个承担开发职责的目录都应有自己的 `README.md`，并按目录用途写成不同风格，而不是统一模板套用。
7. 更完整的组织规范见 [docs/development.md](docs/development.md)。

## 下一步建议

1. 先补一个真实 `tool` 模块，验证项目分层是否顺手。
2. 如果你准备接外部 API 或数据库，我可以继续把 `services/` 和 `schemas/` 基础层一起搭出来。
3. 如果你要接 MCP Client 配置，我也可以顺手补一份示例接入说明。
