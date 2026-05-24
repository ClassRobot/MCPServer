# MCP Server

基于 Python 与 `uv` 构建的 MCP Server 项目骨架，默认集成了官方 `FastMCP` SDK，开箱即用。

## 快速开始

### 1. 本地启动 (Stdio 模式)
适用于 Claude Desktop、Cherry Studio 等客户端本地接入：
```bash
uv sync
uv run playwright install chromium
uv run mcp-server
```

### 2. 本地启动 (流式 HTTP 模式)
```bash
# 默认流式 HTTP 启动
uv run mcp-server --transport streamable-http

# 指定监听地址与端口
uv run mcp-server --transport streamable-http --host 0.0.0.0 --port 8000
```

### 3. Docker 部署 (流式 HTTP 模式)
生产环境下推荐使用 Docker 镜像快速运行（内置 Playwright Chromium）：
```bash
docker build -t mcp-server:prod .
docker run --rm -p 8000:8000 mcp-server:prod
```
> [!NOTE]
> 完整的容器挂载与缓存配置，请参阅 [docs/docker.md](docs/docker.md)。

### 4. Docker 开发模式
开发环境可通过 compose 同时启动 MCP Server 与 PostgreSQL，并挂载本地源码：
```bash
docker compose -f docker-compose.dev.yml up --build
```
> [!NOTE]
> 开发容器说明请参阅 [docs/docker-development.md](docs/docker-development.md)。

---

## 🎁 高阶扩展能力 (Advanced High-Value Extensions)

本项目全新扩展并深度整合了 4 大核心高阶工具能力，完全面向大厂生产规范：

1. **网页视觉快照 (`browser_screenshot_url`)**
   - 驱动 Headless 浏览器对任意 URL 截取高清长图或特定尺寸快照，支持在已登录会话中执行，为大模型注入第一手“网页视觉感知”。
2. **数据图表动态生成器 (`render_data_chart`)**
   - 内置两套高端配色系统（Sleek Light / Harmonious Cyber-Dark HSL 渐变色）。
   - 集成 **Apache ECharts 5.5.0**，智能阻断动画（animation: false），毫秒级极速渲染输出玻璃拟态高级数据图表 PNG 图片。
3. **RPA 登录态与会话持久化 (`browser_save_session_state` / `browser_create_session`)**
   - 支持将会话的 Cookie、LocalStorage 等存储状态（StorageState）以普通 JSON 形式存盘，拉起新会话时一键注入，免除重复手动登录步骤。
4. **零 Poppler 依赖的 PDF 阅读器 (`browser_render_pdf` / `browser_extract_pdf_text`)**
   - 摒弃极其臃肿复杂的 Poppler 依赖，引入 **`pypdfium2`** (Google PDFium) 和 **`pypdf`** 纯 Python 引擎。
   - 提供非阻塞式线程池托管的高清多页视觉光栅化渲染及结构化文本提取能力。

---

## 常用开发命令
```bash
uv sync         # 初始化并同步虚拟环境依赖
uv run pytest   # 运行测试套件
uv run ruff check  # 代码风格与 Lint 检查
uv run ruff format # 代码格式化
```

## 核心环境变量
支持通过环境变量灵活配置服务参数：
- **服务元数据**: `MCP_SERVER_NAME`, `MCP_SERVER_INSTRUCTIONS`
- **HTTP 监听**: `MCP_SERVER_HOST`, `MCP_SERVER_PORT`, `MCP_SERVER_MOUNT_PATH`, `MCP_SERVER_STREAMABLE_HTTP_PATH`
- **日志调试**: `MCP_LOG_LEVEL`, `MCP_LOG_CONSOLE_COLOR`, `MCP_LOG_FILE_PATH`, `MCP_LOG_TOOL_ARGS`

## 项目结构与组织约定
- **[docs/](docs/)**: 存放项目长期维护的设计、架构及环境文档（如 [development.md](docs/development.md)、[docker.md](docs/docker.md)、[docker-development.md](docs/docker-development.md)）。
- **[config/](config/)**: 存放项目级 YAML 配置文件（如 `browser_search.yaml`）。
- **[src/mcp_server/](src/mcp_server/)**: 核心 Python 源码包。
  - `tools/`, `resources/`, `prompts/`: 注册具体 MCP 能力的分层模块。
  - `services/`, `adapters/`, `schemas/`: 应对复杂业务的业务层、外部对接层及数据模型定义层。
- **[tests/](tests/)**: 精确映射源码职责的自动化测试套件。

> [!TIP]
> 新增独立 Tool 或设计新分层时，请先阅读 **[docs/development.md](docs/development.md)**，以确保符合团队代码组织规范与变更原则。
