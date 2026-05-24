"""Resource registration helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.services.query_history import QueryHistoryService

from .project import register_project_resources


def register_resources(
    mcp: FastMCP,
    *,
    query_history_service: QueryHistoryService,
) -> None:
    """Register all MCP resources exposed by this project."""
    register_project_resources(mcp, query_history_service=query_history_service)
