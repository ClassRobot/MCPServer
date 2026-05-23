"""Application assembly for the MCP server scaffold."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import ServerSettings, load_server_settings
from .prompts import register_prompts
from .resources import register_resources
from .tools import register_tools


def create_server(settings: ServerSettings | None = None) -> FastMCP:
    """Create and configure the FastMCP application."""
    active_settings = settings or load_server_settings()
    mcp = FastMCP(
        name=active_settings.name,
        instructions=active_settings.instructions,
        host=active_settings.host,
        port=active_settings.port,
        mount_path=active_settings.mount_path,
        streamable_http_path=active_settings.streamable_http_path,
        stateless_http=active_settings.stateless_http,
        json_response=active_settings.json_response,
    )

    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
    return mcp
