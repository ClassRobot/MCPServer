"""Resource registration helpers."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.services.query_history import QueryHistoryService

from .project import register_project_resources
from .render import register_render_resources


def register_resources(
    mcp: FastMCP,
    *,
    query_history_service: QueryHistoryService,
    render_output_dir: Path,
) -> None:
    """Register all MCP resources exposed by this project."""
    register_project_resources(mcp, query_history_service=query_history_service)
    register_render_resources(mcp, render_output_dir=render_output_dir)
