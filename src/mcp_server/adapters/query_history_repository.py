"""Repository for query history persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database_models import QueryRecordModel


class QueryHistoryRepository:
    """Persist and query query-history rows without embedding business rules."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        query: str,
        provider: str,
        source_tool: str,
        notes: str | None,
    ) -> QueryRecordModel:
        """Insert a new query history row and return the ORM instance."""
        record = QueryRecordModel(
            query=query,
            provider=provider,
            source_tool=source_tool,
            notes=notes,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_recent(self, *, limit: int) -> list[QueryRecordModel]:
        """Return most-recent query history rows ordered by creation time."""
        statement = (
            select(QueryRecordModel).order_by(QueryRecordModel.created_at.desc()).limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
