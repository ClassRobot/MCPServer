"""Tool registration helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .health import register_health_tools


def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools exposed by this project."""
    register_health_tools(mcp)
