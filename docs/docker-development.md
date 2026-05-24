# Docker Development Deployment

这份文档说明如何把项目以开发模式跑在 Docker 中。它和生产镜像是两套用途：生产镜像追求稳定、体积和运行边界；开发容器追求可调试、可挂载源码、可运行测试和迁移。

## 1. 适用场景

开发 Docker 方案适合这些情况：

- 不想在宿主机直接安装 Playwright 浏览器依赖。
- 希望一条命令同时启动 MCP Server 和 PostgreSQL。
- 希望在容器里跑测试、Lint、Alembic migration。
- 希望代码改动后开发服务自动重启。

本地 Conda `classbot-mcp` 仍然保留为宿主机开发方式；Docker 开发模式则完全使用容器内 Python 和容器内 `/opt/venv`。

## 2. 文件组成

- `Dockerfile.dev`
  构建开发镜像，安装 dev 依赖、Playwright Chromium 和系统依赖。
- `docker-compose.dev.yml`
  编排 MCP Server 开发容器与 PostgreSQL 开发数据库。
- `docs/docker.md`
  仍然只描述生产 Docker 镜像。

## 3. 启动开发环境

```bash
docker compose -f docker-compose.dev.yml up --build
```

启动后默认访问：

- MCP HTTP 服务：`http://localhost:8000/mcp`
- PostgreSQL 宿主机端口：`localhost:5433`
- 容器内数据库地址：`postgres:5432`

compose 会在启动 MCP Server 前执行：

```bash
uv sync --frozen --all-groups
uv run --no-sync alembic upgrade head
```

随后用 `watchfiles` 启动服务。修改 `src/`、`config/` 或 `alembic/` 下的 Python / 配置相关文件后，服务进程会自动重启。

## 4. 常用开发命令

```bash
# 后台启动
docker compose -f docker-compose.dev.yml up --build -d

# 查看日志
docker compose -f docker-compose.dev.yml logs -f mcp-server-dev

# 运行测试
docker compose -f docker-compose.dev.yml exec mcp-server-dev uv run --no-sync pytest

# 运行 lint
docker compose -f docker-compose.dev.yml exec mcp-server-dev uv run --no-sync ruff check .

# 手动执行迁移
docker compose -f docker-compose.dev.yml exec mcp-server-dev uv run --no-sync alembic upgrade head

# pyproject.toml 变更后更新锁文件
docker compose -f docker-compose.dev.yml exec mcp-server-dev uv lock

# 关闭容器，保留数据库与缓存 volume
docker compose -f docker-compose.dev.yml down

# 关闭并清理开发数据库、缓存和容器内 venv
docker compose -f docker-compose.dev.yml down -v
```

## 5. 环境变量

可通过 shell 环境变量覆盖开发默认值：

| 变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `MCP_DEV_SERVER_PORT` | `8000` | 映射到宿主机的 MCP HTTP 端口 |
| `MCP_DEV_POSTGRES_PORT` | `5433` | 映射到宿主机的 PostgreSQL 端口 |
| `MCP_DEV_POSTGRES_DB` | `mcp_server` | 开发数据库名 |
| `MCP_DEV_POSTGRES_USER` | `mcp` | 开发数据库用户名 |
| `MCP_DEV_POSTGRES_PASSWORD` | `mcp_dev` | 开发数据库密码 |
| `MCP_DEV_PYTHON_IMAGE` | `python:3.13-slim-bookworm` | 开发镜像使用的 Python 基础镜像 |
| `MCP_DEV_POSTGRES_IMAGE` | `postgres:17-bookworm` | 开发数据库镜像 |

示例：

```bash
MCP_DEV_SERVER_PORT=8100 docker compose -f docker-compose.dev.yml up --build
```

Windows PowerShell 示例：

```powershell
$env:MCP_DEV_SERVER_PORT = "8100"
docker compose -f docker-compose.dev.yml up --build
```

如果 Docker Hub 拉取较慢，可以临时覆盖基础镜像来源：

```powershell
$env:MCP_DEV_PYTHON_IMAGE = "docker.m.daocloud.io/library/python:3.13-slim-bookworm"
$env:MCP_DEV_POSTGRES_IMAGE = "docker.m.daocloud.io/library/postgres:17-bookworm"
docker compose -f docker-compose.dev.yml up --build
```

## 6. 路径与数据约定

开发容器内的关键路径：

- `/workspace`
  宿主机项目根目录 bind mount，代码改动实时进入容器。
- `/opt/venv`
  容器内开发依赖环境，使用 named volume，避免在宿主机项目根目录生成 `.venv`。
- `/data/cache/browser-search`
  浏览器搜索缓存，使用 named volume。
- `/data/logs/mcp-server.log`
  开发容器内本地文件日志，使用 named volume，按天滚动并默认保留 14 天。
- 终端日志默认彩色输出到 `stderr`，文件日志保持纯文本；如果 Docker logs 或终端不需要颜色，可设置 `MCP_LOG_CONSOLE_COLOR=false`。
- `/var/lib/postgresql/data`
  PostgreSQL 数据目录，使用 named volume。

## 7. 与生产 Docker 的区别

| 维度 | 开发 Docker | 生产 Docker |
| :--- | :--- | :--- |
| Dockerfile | `Dockerfile.dev` | `Dockerfile` |
| 依赖 | 包含 dev 依赖 | 只安装运行依赖 |
| 代码 | bind mount 本地源码 | 构建时复制进镜像 |
| 数据库 | compose 内置 PostgreSQL | 外部注入 `DATABASE_URL` |
| 启动 | 自动迁移并监听文件变化 | 固定启动 HTTP MCP 服务 |
| 运行用户 | 非 root | 非 root |
