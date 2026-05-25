# Alembic Migration Workspace

这里维护项目的数据库迁移链路，目标是把数据库结构变更做成可审阅、可回滚、可在多环境重复执行的工程资产。

## 适用场景

- 新增或调整 SQLAlchemy 持久化模型。
- 为生产部署生成可执行的数据库 schema 变更。
- 在本地、CI 或容器环境中统一执行 `upgrade` / `downgrade`。

## 当前约定

- 迁移目标元数据来自 `src/mcp_server/adapters/database.py` 中的 `Base.metadata`。
- 运行时数据库 URL 通过 `DATABASE_URL` 或 `MCP_DATABASE_URL` 注入。
- 正式环境默认面向 PostgreSQL；测试允许使用 SQLite URL 做轻量验证。

## 常用命令

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic revision -m "add_example_table"
```

## 修改迁移时的注意点

1. 先改 ORM 模型，再生成或手写 migration。
2. 非兼容变更优先采用 expand/contract 思路，不要一上来破坏旧列或旧表。
3. 新 migration 合入前，至少验证一次空库升级与已升级库的重复执行行为。
