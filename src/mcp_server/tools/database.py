"""MCP tools for database-backed query history operations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.query_history import QueryHistoryService
from mcp_server.tool_logging import log_mcp_tool


def register_database_tools(
    mcp: FastMCP,
    *,
    query_history_service: QueryHistoryService,
    logging_settings: LoggingSettings,
) -> None:
    """Register database-backed tools that validate persistence wiring end to end."""

    @mcp.tool(
        name="database_record_query",
        description=(
            "Persist a query-history record in the configured database and return "
            "the stored row."
        ),
        structured_output=True,
    )
    @log_mcp_tool("database_record_query", logging_settings)
    async def database_record_query(
        query: str,
        provider: str = "manual",
        source_tool: str = "manual",
        notes: str | None = None,
    ) -> dict[str, Any]:
        record = await query_history_service.record_query(
            query=query,
            provider=provider,
            source_tool=source_tool,
            notes=notes,
        )
        return asdict(record)

    @mcp.tool(
        name="database_list_query_history",
        description=(
            "Read the newest persisted query-history rows from the configured database."
        ),
        structured_output=True,
    )
    @log_mcp_tool("database_list_query_history", logging_settings)
    async def database_list_query_history(limit: int = 10) -> dict[str, Any]:
        records = await query_history_service.list_recent_queries(limit=limit)
        return {
            "count": len(records),
            "records": [asdict(record) for record in records],
        }
