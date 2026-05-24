"""Shared schemas for database-backed MCP data and service responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QueryRecord:
    """Structured query history row returned to services and MCP clients."""

    id: str
    query: str
    provider: str
    source_tool: str
    notes: str | None
    created_at: str


@dataclass(slots=True)
class TaskExecutionRecord:
    """Structured task execution row reserved for future runtime orchestration."""

    id: str
    task_name: str
    status: str
    details_json: str | None
    created_at: str


@dataclass(slots=True)
class PersistedConfigItem:
    """Structured persisted configuration item for shared runtime settings."""

    key: str
    value_json: str
    description: str | None
    created_at: str
    updated_at: str

