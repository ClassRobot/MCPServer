"""Resource registration helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .project import register_project_resources


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources exposed by this project."""
    register_project_resources(mcp)
