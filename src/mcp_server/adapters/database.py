"""Database engine, metadata, and session lifecycle management."""

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

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for persistence models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class DatabaseManager:
    """Own the async SQLAlchemy engine and session factory."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

        if settings.enabled and settings.sqlalchemy_url is not None:
            engine_kwargs: dict[str, Any] = {
                "echo": settings.echo,
                "pool_pre_ping": True,
            }
            if not settings.sqlalchemy_url.startswith("sqlite+aiosqlite://"):
                engine_kwargs["pool_size"] = settings.pool_size
                engine_kwargs["max_overflow"] = settings.max_overflow

            self._engine = create_async_engine(settings.sqlalchemy_url, **engine_kwargs)
            self._session_factory = async_sessionmaker(
                self._engine,
                expire_on_commit=False,
            )

    @property
    def enabled(self) -> bool:
        """Return whether database access is configured for runtime use."""
        return self._engine is not None and self._session_factory is not None

    @property
    def engine(self) -> AsyncEngine:
        """Return the configured async engine or raise if database is disabled."""
        if self._engine is None:
            raise RuntimeError(
                "Database is not configured. Set DATABASE_URL or MCP_DATABASE_URL to enable it."
            )
        return self._engine

    async def initialize(self) -> None:
        """Validate database connectivity during application startup."""
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
        """Dispose the engine when the application shuts down."""
        if self._engine is not None:
            await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield an async session with rollback-on-error behavior."""
        if self._session_factory is None:
            raise RuntimeError(
                "Database is not configured. Set DATABASE_URL or MCP_DATABASE_URL to enable it."
            )

        session = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def _display_url(self) -> str:
        """Return a redacted URL suitable for logs and startup errors."""
        if self._settings.sqlalchemy_url is None:
            return "<unconfigured>"
        return make_url(self._settings.sqlalchemy_url).render_as_string(hide_password=True)
