# Docker Deployment

本 Docker 方案用于将 `mcp-server` 部署于生产环境，默认以 `streamable-http` 模式对外提供服务。

如果需要在 Docker 中进行日常开发、挂载源码、运行测试和启动开发数据库，请使用 [docker-development.md](docker-development.md) 中的开发容器方案。

## 独立运行设计
容器内使用镜像自带的 Python 运行环境与 `uv` 管理依赖，以确保运行时的绝对独立性与可重复性。

- **基础镜像**: 基于 `python:3.13-slim` 进行多阶段构建。
- **环境安全**: 使用非 root 用户运行，保障容器安全。
- **内置服务**: 预装 Playwright Chromium 及其系统依赖。
- **缓存目录**: 默认将浏览器搜索缓存持久化于 `/data/cache/browser-search`。
- **Markdown 输出目录**: 默认将 MarkItDown 转换结果写入 `/data/markitdown`，并通过 `markitdown://{filename}` 资源读取。
- **日志目录**: 默认将本地文件日志写入 `/data/logs/mcp-server.log`。

## 构建与运行

### 1. 构建镜像
```bash
docker build -t mcp-server:prod .
```

默认使用 Debian 官方 apt 源，避免把某个区域镜像站的可用性硬编码进生产构建。若部署网络需要国内镜像，可显式传入构建参数：

```bash
docker build -t mcp-server:prod \
  --build-arg APT_DEBIAN_MIRROR=http://mirrors.aliyun.com/debian \
  --build-arg APT_DEBIAN_SECURITY_MIRROR=http://mirrors.aliyun.com/debian-security \
  .
```

### 2. 运行容器 (流式 HTTP)
```bash
docker run --rm -p 8000:8000 mcp-server:prod
```

### 3. 持久化缓存与挂载配置 (推荐)
```bash
docker run --rm -p 8000:8000 \
  -v mcp-server-data:/data \
  -v /host/path/browser_search.yaml:/app/config/browser_search.yaml:ro \
  mcp-server:prod
```

### 4. 一键部署脚本
Windows PowerShell:
```powershell
.\scripts\deploy-docker.ps1

# 如需指定 apt 镜像源:
.\scripts\deploy-docker.ps1 `
  -AptDebianMirror "http://mirrors.aliyun.com/debian" `
  -AptDebianSecurityMirror "http://mirrors.aliyun.com/debian-security"
```

Linux/macOS:
```bash
sh scripts/deploy-docker.sh

# 如需指定 apt 镜像源:
APT_DEBIAN_MIRROR=http://mirrors.aliyun.com/debian \
APT_DEBIAN_SECURITY_MIRROR=http://mirrors.aliyun.com/debian-security \
sh scripts/deploy-docker.sh
```

## 参数定制与高级配置

### Docker 代理检查
如果构建阶段在 `apt-get update` 或 `playwright install --with-deps chromium` 处失败，并看到类似 `connecting to 127.0.0.1:1080` 的错误，说明 Docker Desktop 配置了手动代理但本机代理未启动。这是宿主机 Docker 网络配置问题，不是项目依赖问题。

可先检查：

```bash
docker info
```

若输出中 `HTTP Proxy` / `HTTPS Proxy` 指向失效端口，请在 Docker Desktop Settings > Resources > Proxies 中关闭手动代理、改成可用代理，或启动对应本地代理后重新构建。

### 端口与路径覆盖
- **端口**: `-e MCP_SERVER_PORT=9000` (映射宿主机端口需同步调整)。
- **缓存位置**: `-e MCP_BROWSER_CACHE_BASE_DIR=/data/custom-cache`。
- **MarkItDown 输出目录**: `-e MCP_MARKITDOWN_OUTPUT_DIR=/data/markitdown`。
- **MarkItDown 读取白名单**: `-e MCP_MARKITDOWN_ALLOWED_ROOTS=/app:/data`。
- **日志文件**: `-e MCP_LOG_FILE_PATH=/data/logs/custom.log`。
- **终端日志颜色**: `-e MCP_LOG_CONSOLE_COLOR=false` 可关闭 Docker logs 中的 ANSI 彩色输出。
- **配置文件**: `-e MCP_BROWSER_CONFIG_PATH=/config/custom.yaml` 并挂载对应配置文件。

### 常用环境变量
支持以下主要环境变量配置：

```properties
# 服务配置
MCP_SERVER_NAME, MCP_SERVER_INSTRUCTIONS, MCP_SERVER_HOST, MCP_SERVER_PORT, MCP_SERVER_MOUNT_PATH

# 浏览器会话
MCP_BROWSER_CONFIG_PATH, MCP_BROWSER_CACHE_BASE_DIR, MCP_BROWSER_HEADLESS, MCP_BROWSER_TIMEOUT_MS, MCP_BROWSER_SESSION_TTL_SEC

# 搜索与过滤
MCP_BROWSER_DEFAULT_PROVIDER, MCP_BROWSER_MAX_RESULTS, MCP_BROWSER_CACHE_ENABLED, MCP_BROWSER_CACHE_TTL_SEC, MCP_BROWSER_CACHE_MAX_ENTRIES, MCP_BROWSER_FILTER_ADS_ENABLED

# 日志
MCP_LOGGING_CONFIG_PATH, MCP_LOG_LEVEL, MCP_LOG_CONSOLE_ENABLED, MCP_LOG_CONSOLE_COLOR, MCP_LOG_FILE_ENABLED, MCP_LOG_FILE_PATH, MCP_LOG_RETENTION_DAYS, MCP_LOG_TOOL_ARGS

# MarkItDown
MCP_MARKITDOWN_CONFIG_PATH, MCP_MARKITDOWN_ENABLED, MCP_MARKITDOWN_ALLOWED_ROOTS, MCP_MARKITDOWN_OUTPUT_DIR, MCP_MARKITDOWN_MAX_INPUT_BYTES, MCP_MARKITDOWN_SAVE_OUTPUT
```

## 运行边界
- 容器方案专为主打流式 HTTP 模式设计，暂不以 stdio 作为主要容器运行场景。
