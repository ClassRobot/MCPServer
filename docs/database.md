# Database Integration Notes

这份文档记录当前 MCP 项目的数据库技术决策与落地边界，重点不是“如何把所有数据都塞进数据库”，而是“如何先把一套稳定的数据基础设施搭好”。

## 1. 当前决策

### 为什么默认选 PostgreSQL

这个项目的目标不是单机脚本，而是可继续演进为多实例、可容器化部署、带迁移管理的长期服务。因此数据库主方案直接定为 PostgreSQL：

- 更适合并发写入、长期运行和后续扩表。
- 对索引、审计字段、迁移和生产部署的支持成熟。
- 后面如果加入任务记录、共享配置、查询历史或更复杂的检索元数据，不需要再做主库迁移。

### 接入栈

- `SQLAlchemy 2.x`: 数据访问抽象与 ORM 模型。
- `Alembic`: schema migration 管理。
- `asyncpg`: PostgreSQL 异步驱动。

补充说明：MCP 没有“专用数据库包”。这里的数据库接入，本质上仍然是常规 Python 服务的工程化接入。

## 2. 分层落点

数据库能力按当前项目分层接入，而不是把 SQL 或连接逻辑散落在 tool 中：

```mermaid
flowchart LR
    Tool["tools/database.py"] --> Service["services/query_history.py"]
    Service --> Repo["adapters/query_history_repository.py"]
    Repo --> DB["adapters/database.py"]
    DB --> PG["PostgreSQL / SQLite(test only)"]
    Service --> Schema["schemas/database.py"]
```

各层职责如下：

- `config.py`
  负责加载 `DATABASE_URL`、连接池与开关配置。
- `adapters/database.py`
  负责 engine、session factory、连接初始化与关闭。
- `adapters/database_models.py`
  负责 ORM 模型定义。
- `adapters/query_history_repository.py`
  负责最小持久化读写，不承载业务规则。
- `services/query_history.py`
  负责输入规整、事务边界内的业务读写编排。
- `tools/database.py`
  负责把数据库能力作为 MCP Tool 暴露出来做链路验证。

## 3. 当前第一版包含什么

第一版数据库基础设施只覆盖这些内容：

- 数据库配置读取与 URL 规范化。
- SQLAlchemy async engine 与 session 管理。
- Alembic 迁移目录与首个 migration。
- 三张最小持久化表：
  - `query_records`
  - `task_execution_records`
  - `persisted_config_items`
- 一条完整验证链路：
  - `database_record_query`
  - `database_list_query_history`

还没有做的事：

- 没有把现有文件缓存强制迁库。
- 没有引入 Redis、消息队列或混合双主数据库方案。
- 没有在 Tool 层直接暴露 ORM 或原始 SQL。

## 4. 配置方式

运行时重点环境变量：

| 变量 | 作用 | 默认 |
| :--- | :--- | :--- |
| `DATABASE_URL` / `MCP_DATABASE_URL` | 主数据库连接串 | 无 |
| `MCP_DATABASE_ENABLED` | 显式启停数据库 | URL 存在时自动启用 |
| `MCP_DATABASE_ECHO` | SQLAlchemy SQL 输出 | `false` |
| `MCP_DATABASE_POOL_SIZE` | 连接池大小 | `5` |
| `MCP_DATABASE_MAX_OVERFLOW` | 连接池溢出连接数 | `10` |

示例：

```bash
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mcp_server
uv sync
uv run alembic upgrade head
uv run mcp-server --transport streamable-http
```

代码运行时会自动把 PostgreSQL URL 规范化为 `postgresql+asyncpg://...`。  
测试时允许使用 `sqlite://...`，内部会被转成 `sqlite+aiosqlite://...`，这样不用起本地 PostgreSQL 也能跑回归。

## 5. 开发与部署建议

### 本地开发

- 推荐使用 `uv` 自动管理的虚拟环境或任意 Python 3.11+ 运行环境。
- 依赖同步通过 `uv sync` 完成，确保依赖版本与 `uv.lock` 保持严格一致。
- 数据库服务建议单独跑 PostgreSQL 容器或本机实例，不要把业务运行时和宿主机 Conda 环境混在一起理解。

### 生产部署

- 应用容器中的 Python 运行时来自镜像自身，不来自宿主机 Conda。
- 数据库 URL 通过环境变量注入容器。
- 迁移可在部署前单独执行，或由发布流程显式执行 `alembic upgrade head`。

## 6. 后续扩展顺序

推荐后续沿着这个顺序继续演进：

1. 先稳定查询历史、任务记录和共享配置这些基础表。
2. 再决定是否把文件缓存迁移为数据库缓存。
3. 若未来出现高频热点与异步队列场景，再补 Redis，而不是让 Redis 取代主数据库。
