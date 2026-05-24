# Docker Deployment

本 Docker 方案用于将 `mcp-server` 部署于生产环境，默认以 `streamable-http` 模式对外提供服务。

## 独立运行设计
容器内使用镜像自带的 Python 运行环境与 `uv` 管理依赖，以确保运行时的绝对独立性与可重复性。

- **基础镜像**: 基于 `python:3.13-slim` 进行多阶段构建。
- **环境安全**: 使用非 root 用户运行，保障容器安全。
- **内置服务**: 预装 Playwright Chromium 及其系统依赖。
- **缓存目录**: 默认将浏览器搜索缓存持久化于 `/data/cache/browser-search`。

## 构建与运行

### 1. 构建镜像
```bash
docker build -t mcp-server:prod .
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

## 参数定制与高级配置

### 端口与路径覆盖
- **端口**: `-e MCP_SERVER_PORT=9000` (映射宿主机端口需同步调整)。
- **缓存位置**: `-e MCP_BROWSER_CACHE_BASE_DIR=/data/custom-cache`。
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
```

## 运行边界
- 容器方案专为主打流式 HTTP 模式设计，暂不以 stdio 作为主要容器运行场景。


