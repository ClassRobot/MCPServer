"""Business logic for persistent query history operations."""

from __future__ import annotations

from mcp_server.adapters.database import DatabaseManager
from mcp_server.adapters.database_models import QueryRecordModel
from mcp_server.adapters.query_history_repository import QueryHistoryRepository
from mcp_server.schemas.database import QueryRecord


class QueryHistoryService:
    """Record and retrieve query-history entries through the database layer."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    async def record_query(
        self,
        *,
        query: str,
        provider: str,
        source_tool: str,
        notes: str | None = None,
    ) -> QueryRecord:
        """Persist a normalized query-history row and return structured data."""
        normalized_query = self._normalize_non_empty(query, field_name="query")
        normalized_provider = self._normalize_non_empty(provider, field_name="provider")
        normalized_source_tool = self._normalize_non_empty(
            source_tool,
            field_name="source_tool",
        )
        normalized_notes = notes.strip() if notes is not None else None

        async with self._database_manager.session() as session:
            repository = QueryHistoryRepository(session)
            record = await repository.create(
                query=normalized_query,
                provider=normalized_provider,
                source_tool=normalized_source_tool,
                notes=normalized_notes or None,
            )
            await session.commit()
            return self._to_schema(record)

    async def list_recent_queries(self, *, limit: int = 10) -> list[QueryRecord]:
        """Return the newest persisted query-history rows."""
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")

        async with self._database_manager.session() as session:
            repository = QueryHistoryRepository(session)
            records = await repository.list_recent(limit=limit)
            return [self._to_schema(record) for record in records]

    def _normalize_non_empty(self, value: str, *, field_name: str) -> str:
        """Normalize a required string field and reject empty values."""
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized

    def _to_schema(self, record: QueryRecordModel) -> QueryRecord:
        """Map ORM rows into MCP-safe structured output objects."""
        return QueryRecord(
            id=record.id,
            query=record.query,
            provider=record.provider,
            source_tool=record.source_tool,
            notes=record.notes,
            created_at=record.created_at.isoformat(),
        )
