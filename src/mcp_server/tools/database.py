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
            "Persist a query-history record in the configured database and return the stored row."
        ),
    )
    @log_mcp_tool("database_record_query", logging_settings)
    async def database_record_query(
        query: str,
        provider: str = "manual",
        source_tool: str = "manual",
        notes: str | None = None,
    ) -> list[Any]:
        from mcp.types import TextContent

        record = await query_history_service.record_query(
            query=query,
            provider=provider,
            source_tool=source_tool,
            notes=notes,
        )
        return [
            TextContent(
                type="text",
                text=f"Successfully recorded query (ID: {record.id}) at {record.created_at}",
            )
        ]

    @mcp.tool(
        name="database_list_query_history",
        description=("Read the newest persisted query-history rows from the configured database."),
    )
    @log_mcp_tool("database_list_query_history", logging_settings)
    async def database_list_query_history(limit: int = 10) -> list[Any]:
        from mcp.types import TextContent

        records = await query_history_service.list_recent_queries(limit=limit)
        if not records:
            return [TextContent(type="text", text="No query history found.")]

        lines = [f"Showing last {len(records)} query records:", ""]
        for record in records:
            lines.append(f"- [{record.created_at}] {record.query} ({record.provider})")

        return [TextContent(type="text", text="\n".join(lines))]
