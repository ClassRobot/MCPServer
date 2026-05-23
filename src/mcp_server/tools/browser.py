"""MCP tools for browser-driven search and low-level browser automation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import ServerSettings
from mcp_server.services.browser_search import BrowserSearchService


def register_browser_tools(
    mcp: FastMCP,
    *,
    settings: ServerSettings,
    browser_search_service: BrowserSearchService,
    session_manager: BrowserSessionManager,
) -> None:
    """Register browser search and low-level browser automation tools."""

    @mcp.tool(
        name="browser_search",
        description=(
            "Run a browser-driven search on public search pages and return "
            "structured results."
        ),
        structured_output=True,
    )
    async def browser_search(
        query: str,
        provider: str = "bing",
        max_results: int | None = None,
        include_summary: bool = False,
        use_cache: bool = True,
        force_refresh: bool = False,
        filter_ads: bool = True,
    ) -> dict[str, Any]:
        response = await browser_search_service.search(
            query=query,
            provider=provider or settings.browser_search.browser.default_provider,
            max_results=max_results,
            include_summary=include_summary,
            use_cache=use_cache,
            force_refresh=force_refresh,
            filter_ads=filter_ads,
        )
        return asdict(response)

    @mcp.tool(
        name="browser_create_session",
        description="Create a reusable browser session for low-level page operations.",
        structured_output=True,
    )
    async def browser_create_session(headless: bool | None = None) -> dict[str, Any]:
        session_info = await session_manager.create_session(headless=headless)
        return asdict(session_info)

    @mcp.tool(
        name="browser_open",
        description="Open a URL inside an existing browser session.",
        structured_output=True,
    )
    async def browser_open(session_id: str, url: str) -> dict[str, Any]:
        return await session_manager.open(session_id, url)

    @mcp.tool(
        name="browser_fill",
        description="Fill an input field inside an existing browser session.",
        structured_output=True,
    )
    async def browser_fill(
        session_id: str,
        selector: str,
        value: str,
        clear: bool = True,
    ) -> dict[str, Any]:
        return await session_manager.fill(session_id, selector, value, clear=clear)

    @mcp.tool(
        name="browser_click",
        description="Click an element inside an existing browser session.",
        structured_output=True,
    )
    async def browser_click(
        session_id: str,
        selector: str,
        wait_for_network_idle: bool = True,
    ) -> dict[str, Any]:
        return await session_manager.click(
            session_id,
            selector,
            wait_for_network_idle=wait_for_network_idle,
        )

    @mcp.tool(
        name="browser_extract",
        description="Extract text and optional links from the current browser page.",
        structured_output=True,
    )
    async def browser_extract(
        session_id: str,
        selector: str | None = None,
        include_links: bool = False,
        max_links: int = 10,
    ) -> dict[str, Any]:
        extracted = await session_manager.extract(
            session_id=session_id,
            selector=selector,
            include_links=include_links,
            max_links=max_links,
        )
        return asdict(extracted)

    @mcp.tool(
        name="browser_close_session",
        description="Close an existing browser session.",
        structured_output=True,
    )
    async def browser_close_session(session_id: str) -> dict[str, Any]:
        return await session_manager.close_session(session_id)
