"""SQLAlchemy ORM models for persistent application data."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp for persistence defaults."""
    return datetime.now(UTC)


def _new_id() -> str:
    """Generate compact stable identifiers for persistence rows."""
    return uuid4().hex


class QueryRecordModel(Base):
    """Persisted history of user-facing or tool-driven query requests."""

    __tablename__ = "query_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_tool: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        index=True,
    )


class TaskExecutionRecordModel(Base):
    """Persisted execution metadata for future background or scheduled tasks."""

    __tablename__ = "task_execution_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    task_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        index=True,
    )


class PersistedConfigItemModel(Base):
    """Persisted key-value settings intended for shared runtime configuration."""

    __tablename__ = "persisted_config_items"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

