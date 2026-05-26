"""异步 SQLAlchemy 数据库引擎与会话生命周期管理器。

提供统一的 ORM 基类（带有自适应命名约定）、连接池初始化配置、
异步会话工厂创建以及支持自动回滚的 Session 上下文管理器。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from mcp_server.config import DatabaseSettings

# 数据库索引与约束的标准命名规约，确保在不同 DBMS 之间迁移时命名的一致性，防止 Alembic 迁移工具发生名称冲突。
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """ORM 声明式映射基类。

    为所有的持久化数据模型（如 QueryRecord）提供统一的元数据定义与命名约束。
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class DatabaseManager:
    """数据库管理器类。

    封装异步 SQLAlchemy 物理引擎实例与会话生成工厂，提供高可靠性的连接。
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        """初始化数据库管理器，延迟拉起连接池。

        Args:
            settings (DatabaseSettings): 持久化层全局配置。
        """
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

        if settings.enabled and settings.sqlalchemy_url is not None:
            engine_kwargs: dict[str, Any] = {
                "echo": settings.echo,
                "pool_pre_ping": True,  # 每次获取链接时预先发送 PING，自动重连失效链接，防止 MySQL/Postgres 抛出断开连接异常
            }
            # SQLite 数据库使用 aiosqlite，不需要也不支持配置 pool_size 和 max_overflow
            if not settings.sqlalchemy_url.startswith("sqlite+aiosqlite://"):
                engine_kwargs["pool_size"] = settings.pool_size
                engine_kwargs["max_overflow"] = settings.max_overflow

            self._engine = create_async_engine(settings.sqlalchemy_url, **engine_kwargs)
            self._session_factory = async_sessionmaker(
                self._engine,
                expire_on_commit=False,  # 提交时不令 ORM 对象失效，防止事务外读取发生 DetachedInstanceError 异常
            )

    @property
    def enabled(self) -> bool:
        """返回当前数据库服务是否已成功配置并准备就绪。"""
        return self._engine is not None and self._session_factory is not None

    @property
    def engine(self) -> AsyncEngine:
        """获取异步 SQLAlchemy 物理引擎句柄。

        Raises:
            RuntimeError: 当数据库未配置或处于禁用状态时抛出。
        """
        if self._engine is None:
            raise RuntimeError(
                "Database is not configured. Set DATABASE_URL or MCP_DATABASE_URL to enable it."
            )
        return self._engine

    async def initialize(self) -> None:
        """服务启动前的预检（Pre-flight check）机制。

        【健康检查算法说明】：
        - 服务启动时向物理数据库发送极轻量的 `SELECT 1` 指令，验证物理网络与授权是否完全连通。
        - 预检失败会立即抛出运行时异常，防止在运行时执行 Tool 调用才暴露连接故障。
        """
        if not self.enabled:
            return

        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise RuntimeError(
                f"Failed to connect to database {self._display_url()}: {exc}"
            ) from exc

    async def dispose(self) -> None:
        """服务关闭时优雅释放并断开引擎连接池。"""
        if self._engine is not None:
            await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """开启并产出一个具备事务自动处理 and 回滚屏障（Barriers）的异步 Session 会话。

        【事务异常隔离算法说明】：
        1. 采用 `asynccontextmanager` 生成一个作用域。
        2. 当作用域正常结束时，自动执行 `commit()` 提交当前事务。
        3. 若在作用域内部发生任何未捕获的业务异常（如 SQLAlchemy 报错），
           立刻执行 `rollback()` 回滚所有未提交的写操作，随后将异常向上抛出，
           最终在 `finally` 块中执行 `close()` 释放链接回连接池，彻底防止链接泄露。
        """
        if self._session_factory is None:
            raise RuntimeError(
                "Database is not configured. Set DATABASE_URL or MCP_DATABASE_URL to enable it."
            )

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def _display_url(self) -> str:
        """处理敏感的连接数据库串，用于安全的控制台日志展示（隐去用户密码）。"""
        if not self._settings.sqlalchemy_url:
            return "n/a"
        try:
            url = make_url(self._settings.sqlalchemy_url)
            return url.render_as_string(hide_password=True)
        except Exception:
            return "unknown-db"
