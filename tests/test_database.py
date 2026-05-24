"""Tests for database configuration, migrations, and query-history services."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from mcp_server.adapters.database import Base, DatabaseManager
from mcp_server.config import DatabaseSettings, load_server_settings
from mcp_server.services.query_history import QueryHistoryService


def test_load_server_settings_reads_database_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@localhost:5432/mcp_server")
    monkeypatch.setenv("MCP_DATABASE_ECHO", "true")
    monkeypatch.setenv("MCP_DATABASE_POOL_SIZE", "8")
    monkeypatch.setenv("MCP_DATABASE_MAX_OVERFLOW", "12")

    settings = load_server_settings()

    assert settings.database.enabled is True
    assert settings.database.echo is True
    assert settings.database.pool_size == 8
    assert settings.database.max_overflow == 12
    assert settings.database.sqlalchemy_url == (
        "postgresql+asyncpg://user:secret@localhost:5432/mcp_server"
    )


def test_load_server_settings_rejects_enabled_database_without_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MCP_DATABASE_URL", raising=False)
    monkeypatch.setenv("MCP_DATABASE_ENABLED", "true")

    with pytest.raises(ValueError, match="MCP_DATABASE_ENABLED is true"):
        load_server_settings()


@pytest.mark.asyncio
async def test_database_manager_and_query_history_service_round_trip(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "query-history.sqlite3"
    manager = DatabaseManager(
        DatabaseSettings(enabled=True, sqlalchemy_url=f"sqlite:///{database_path}")
    )
    service = QueryHistoryService(manager)

    try:
        async with manager.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        await manager.initialize()

        first_record = await service.record_query(
            query="  python mcp  ",
            provider=" manual ",
            source_tool=" cli ",
            notes="  smoke test  ",
        )
        await service.record_query(
            query="database migration",
            provider="manual",
            source_tool="cli",
        )
        recent_records = await service.list_recent_queries(limit=5)

        assert first_record.query == "python mcp"
        assert first_record.provider == "manual"
        assert first_record.source_tool == "cli"
        assert first_record.notes == "smoke test"
        assert len(recent_records) == 2
        assert recent_records[0].query == "database migration"
        assert recent_records[1].query == "python mcp"
    finally:
        await manager.dispose()


@pytest.mark.asyncio
async def test_database_manager_session_requires_configuration() -> None:
    manager = DatabaseManager(DatabaseSettings())

    with pytest.raises(RuntimeError, match="Database is not configured"):
        async with manager.session():
            pytest.fail("session() should not yield when the database is disabled.")


def test_alembic_upgrade_creates_initial_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "migration.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.delenv("MCP_DATABASE_URL", raising=False)
    monkeypatch.delenv("MCP_DATABASE_ENABLED", raising=False)

    alembic_config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini")
    )

    command.upgrade(alembic_config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)

    try:
        assert set(inspector.get_table_names()) >= {
            "persisted_config_items",
            "query_records",
            "task_execution_records",
        }
        assert {
            index["name"] for index in inspector.get_indexes("query_records")
        } == {"ix_query_records_created_at", "ix_query_records_provider"}
        assert {
            index["name"] for index in inspector.get_indexes("task_execution_records")
        } == {
            "ix_task_execution_records_created_at",
            "ix_task_execution_records_task_name",
        }
    finally:
        engine.dispose()
