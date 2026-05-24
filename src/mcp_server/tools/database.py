"""MCP tools for database-backed query history operations."""

from __future__ import annotations

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
            "Permanently record a search query and its metadata into the persistent database. "
            "Useful for auditing, history tracking, and future query optimization."
        ),
    )
    @log_mcp_tool("database_record_query", logging_settings)
    async def database_record_query(
        query: str,
        provider: str = "manual",
        source_tool: str = "manual",
        notes: str | None = None,
    ) -> list[Any]:
        """Save a query record.

        Args:
            query: The actual search string or question that was asked.
            provider: The name of the service provider used (e.g., 'bing', 'internal').
            source_tool: The name of the tool that triggered this record.
            notes: Optional additional context or observations about the query.
        """
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
        description=(
            "Retrieve a list of the most recent query records from the database. "
            "Allows the AI to see past interactions and maintain context over time."
        ),
    )
    @log_mcp_tool("database_list_query_history", logging_settings)
    async def database_list_query_history(limit: int = 10) -> list[Any]:
        """List recent queries.

        Args:
            limit: Maximum number of records to retrieve (default: 10).
        """
        from mcp.types import TextContent

        records = await query_history_service.list_recent_queries(limit=limit)
        if not records:
            return [TextContent(type="text", text="No query history found.")]

        lines = [f"Showing last {len(records)} query records:", ""]
        for record in records:
            lines.append(f"- [{record.created_at}] {record.query} ({record.provider})")

        return [TextContent(type="text", text="\n".join(lines))]
