"""Small verification tools for client connectivity and request flow."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def ping() -> str:
    """Return a simple health-check response."""
    return "pong"


def echo(message: str) -> str:
    """Return the original message so client integration is easy to verify."""
    return message


def register_health_tools(mcp: FastMCP) -> None:
    """Register connectivity-oriented tools on the FastMCP application."""
    mcp.tool()(ping)
    mcp.tool()(echo)
