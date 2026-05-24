"""Small verification tools for client connectivity and request flow."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.tool_logging import log_mcp_tool


def ping() -> str:
    """Return a simple health-check response."""
    return "pong"


def echo(message: str) -> str:
    """Return the original message so client integration is easy to verify."""
    return message


def register_health_tools(
    mcp: FastMCP,
    *,
    logging_settings: LoggingSettings,
) -> None:
    """Register connectivity-oriented tools on the FastMCP application."""
    mcp.tool()(log_mcp_tool("ping", logging_settings)(ping))
    mcp.tool()(log_mcp_tool("echo", logging_settings)(echo))
