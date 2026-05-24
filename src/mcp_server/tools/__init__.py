"""Tool registration helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import ServerSettings
from mcp_server.services.browser_search import BrowserSearchService
from mcp_server.services.pdf_reader import PDFReadingService
from mcp_server.services.query_history import QueryHistoryService
from mcp_server.services.rendering import ContentRenderingService

from .browser import register_browser_tools
from .database import register_database_tools
from .health import register_health_tools
from .pdf import register_pdf_tools
from .rendering import register_rendering_tools


def register_tools(
    mcp: FastMCP,
    *,
    settings: ServerSettings,
    browser_search_service: BrowserSearchService,
    session_manager: BrowserSessionManager,
    query_history_service: QueryHistoryService,
    rendering_service: ContentRenderingService,
    pdf_service: PDFReadingService,
) -> None:
    """Register all MCP tools exposed by this project."""
    register_health_tools(mcp, logging_settings=settings.logging)
    register_database_tools(
        mcp,
        query_history_service=query_history_service,
        logging_settings=settings.logging,
    )
    register_browser_tools(
        mcp,
        settings=settings,
        browser_search_service=browser_search_service,
        session_manager=session_manager,
    )
    register_rendering_tools(
        mcp,
        rendering_service=rendering_service,
        logging_settings=settings.logging,
    )
    register_pdf_tools(
        mcp,
        pdf_service=pdf_service,
        project_root=settings.project_root,
        logging_settings=settings.logging,
    )
