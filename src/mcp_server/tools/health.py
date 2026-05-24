"""Small verification tools for client connectivity and request flow."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.tool_logging import log_mcp_tool


def ping() -> str:
    """Return a simple 'pong' health-check response to verify the server is alive."""
    return "pong"


def echo(message: str) -> str:
    """Verify end-to-end request flow by returning the exact message sent by the client.

    Args:
        message: Any string to be echoed back.
    """
    return message


def register_health_tools(
    mcp: FastMCP,
    *,
    logging_settings: LoggingSettings,
) -> None:
    """Register basic connectivity and diagnostic tools."""
    mcp.tool(
        name="ping",
        description="A minimal heartbeat tool to check if the MCP server is responsive.",
    )(log_mcp_tool("ping", logging_settings)(ping))

    mcp.tool(
        name="echo",
        description="A diagnostic tool that echoes back the input message to verify connectivity.",
    )(log_mcp_tool("echo", logging_settings)(echo))
