"""Tool registration helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import ServerSettings
from mcp_server.services.browser_search import BrowserSearchService

from .browser import register_browser_tools
from .health import register_health_tools


def register_tools(
    mcp: FastMCP,
    *,
    settings: ServerSettings,
    browser_search_service: BrowserSearchService,
    session_manager: BrowserSessionManager,
) -> None:
    """Register all MCP tools exposed by this project."""
    register_health_tools(mcp)
    register_browser_tools(
        mcp,
        settings=settings,
        browser_search_service=browser_search_service,
        session_manager=session_manager,
    )
