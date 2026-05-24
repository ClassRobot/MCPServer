"""Application assembly for the MCP server scaffold."""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .adapters.bing_provider import BingSearchProvider
from .adapters.browser_session import BrowserSessionManager
from .adapters.database import DatabaseManager
from .adapters.search_cache import SearchCacheStore
from .config import ServerSettings, load_server_settings
from .prompts import register_prompts
from .resources import register_resources
from .services.browser_search import BrowserSearchService
from .services.pdf_reader import PDFReadingService
from .services.query_history import QueryHistoryService
from .services.rendering import ContentRenderingService
from .services.search_results import SearchResultFilter
from .tools import register_tools


def create_server(settings: ServerSettings | None = None) -> FastMCP:
    """Create and configure the FastMCP application."""
    active_settings = settings or load_server_settings()

    # Infrastructure
    session_manager = BrowserSessionManager(active_settings.browser_search.browser)
    cache_store = SearchCacheStore(active_settings.browser_search.cache)
    database_manager = DatabaseManager(active_settings.database)

    # Domain Services
    result_filter = SearchResultFilter(active_settings.browser_search.filter)
    browser_search_service = BrowserSearchService(
        session_manager=session_manager,
        cache_store=cache_store,
        providers={"bing": BingSearchProvider(active_settings.browser_search.browser)},
        result_filter=result_filter,
        browser_settings=active_settings.browser_search.browser,
        cache_settings=active_settings.browser_search.cache,
    )
    rendering_service = ContentRenderingService(
        session_manager=session_manager,
        default_output_dir=active_settings.render_output_dir,
    )
    query_history_service = QueryHistoryService(database_manager)
    pdf_service = PDFReadingService(default_output_dir=active_settings.render_output_dir)

    @asynccontextmanager
    async def lifespan(_: FastMCP):
        try:
            await database_manager.initialize()
            yield
        finally:
            await database_manager.dispose()
            await session_manager.close_all()

    mcp = FastMCP(
        name=active_settings.name,
        instructions=active_settings.instructions,
        host=active_settings.host,
        port=active_settings.port,
        mount_path=active_settings.mount_path,
        streamable_http_path=active_settings.streamable_http_path,
        stateless_http=active_settings.stateless_http,
        json_response=active_settings.json_response,
        lifespan=lifespan,
    )

    register_tools(
        mcp,
        settings=active_settings,
        browser_search_service=browser_search_service,
        session_manager=session_manager,
        query_history_service=query_history_service,
        rendering_service=rendering_service,
        pdf_service=pdf_service,
    )
    register_resources(
        mcp,
        query_history_service=query_history_service,
        render_output_dir=active_settings.render_output_dir,
    )
    register_prompts(mcp)
    return mcp
