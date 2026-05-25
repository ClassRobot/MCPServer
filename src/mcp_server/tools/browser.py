"""MCP tools for browser-driven search and low-level browser automation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import ServerSettings
from mcp_server.services.browser_search import BrowserSearchService
from mcp_server.tool_logging import log_mcp_tool


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
            "Execute a comprehensive browser-driven search using public search engines."
            " Returns structured search results including titles, URLs, and snippets."
            " Best used for gathering real-time information from the web."
        ),
    )
    @log_mcp_tool("browser_search", settings.logging)
    async def browser_search(
        query: str,
        provider: str = "bing",
        max_results: int | None = None,
        include_summary: bool = False,
        use_cache: bool = True,
        force_refresh: bool = False,
        filter_ads: bool = True,
    ) -> list[Any]:
        """Run a web search and return results.

        Args:
            query: The search keywords or natural language question.
            provider: The search engine provider to use (currently supports 'bing').
            max_results: Maximum number of search results to return.
            include_summary: Whether to include an AI-generated summary (if supported).
            use_cache: If True, returns cached results if available.
            force_refresh: If True, bypasses the cache and performs a fresh search.
            filter_ads: Whether to exclude advertisements and sponsored content.
        """
        from mcp.types import TextContent

        response = await browser_search_service.search(
            query=query,
            provider=provider or settings.browser_search.browser.default_provider,
            max_results=max_results,
            include_summary=include_summary,
            use_cache=use_cache,
            force_refresh=force_refresh,
            filter_ads=filter_ads,
        )

        lines = [f"Search results for '{query}' via {response.provider}:", ""]
        if not response.results:
            lines.append("No results found.")
        else:
            for i, res in enumerate(response.results, 1):
                lines.append(f"{i}. **{res.title}**")
                lines.append(f"   URL: {res.url}")
                if res.snippet:
                    lines.append(f"   Snippet: {res.snippet}")
                lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    @mcp.tool(
        name="browser_create_session",
        description=(
            "Initialize a new stateful browser session. "
            "Allows for complex multi-step interactions (e.g., login, form filling). "
            "Can optionally load a saved storage state (cookies, localStorage) by state_name."
        ),
        structured_output=True,
    )
    @log_mcp_tool("browser_create_session", settings.logging)
    async def browser_create_session(
        headless: bool | None = None,
        state_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a reusable browser session.

        Args:
            headless: Whether to run the browser in headless mode (default: True).
            state_name: Optional name of a previously saved session state to restore.
        """
        storage_state_path = None
        if state_name:
            import re

            if not re.match(r"^[a-zA-Z0-9_-]+$", state_name):
                raise ValueError(
                    "Invalid state_name. Use only letters, numbers, underscores, and hyphens."
                )

            state_file = settings.sessions_dir / f"{state_name}.json"
            if state_file.exists():
                storage_state_path = str(state_file)

        session_info = await session_manager.create_session(
            headless=headless,
            storage_state_path=storage_state_path,
        )
        return asdict(session_info)

    @mcp.tool(
        name="browser_open",
        description="Navigate to a specific URL within an active browser session.",
        structured_output=True,
    )
    @log_mcp_tool("browser_open", settings.logging)
    async def browser_open(session_id: str, url: str) -> dict[str, Any]:
        """Open a URL in a session.

        Args:
            session_id: The ID of the active browser session.
            url: The destination web address.
        """
        return await session_manager.open(session_id, url)

    @mcp.tool(
        name="browser_fill",
        description="Type text into an input field or textarea identified by a CSS selector.",
        structured_output=True,
    )
    @log_mcp_tool("browser_fill", settings.logging)
    async def browser_fill(
        session_id: str,
        selector: str,
        value: str,
        clear: bool = True,
    ) -> dict[str, Any]:
        """Fill an input field.

        Args:
            session_id: The ID of the active browser session.
            selector: The CSS selector of the input element (e.g., 'input[name="q"]', '#search').
            value: The text content to enter.
            clear: Whether to clear the field before typing (default: True).
        """
        return await session_manager.fill(session_id, selector, value, clear=clear)

    @mcp.tool(
        name="browser_click",
        description=(
            "Click a button, link, or other clickable element identified by a CSS selector."
        ),
        structured_output=True,
    )
    @log_mcp_tool("browser_click", settings.logging)
    async def browser_click(
        session_id: str,
        selector: str,
        wait_for_network_idle: bool = True,
    ) -> dict[str, Any]:
        """Click an element.

        Args:
            session_id: The ID of the active browser session.
            selector: The CSS selector of the element to click.
            wait_for_network_idle: Whether to wait for network requests to finish after the click.
        """
        return await session_manager.click(
            session_id,
            selector,
            wait_for_network_idle=wait_for_network_idle,
        )

    @mcp.tool(
        name="browser_extract",
        description=(
            "Extract structured text and links from the current page. "
            "Can be scoped to a specific element using a CSS selector."
        ),
    )
    @log_mcp_tool("browser_extract", settings.logging)
    async def browser_extract(
        session_id: str,
        selector: str | None = None,
        include_links: bool = False,
        max_links: int = 10,
    ) -> list[Any]:
        """Extract content from the page.

        Args:
            session_id: The ID of the active browser session.
            selector: Optional CSS selector to limit extraction to a specific element.
            include_links: Whether to extract hyperlinks found within the content.
            max_links: Maximum number of links to return if include_links is True.
        """
        from mcp.types import TextContent

        extracted = await session_manager.extract(
            session_id=session_id,
            selector=selector,
            include_links=include_links,
            max_links=max_links,
        )

        lines = [
            f"Extracted from: {extracted.url}",
            f"Title: {extracted.title}",
            "",
            extracted.text,
        ]

        if extracted.links:
            lines.append("\n--- Links ---")
            for link in extracted.links:
                lines.append(f"- {link.text}: {link.url}")

        return [TextContent(type="text", text="\n".join(lines))]

    @mcp.tool(
        name="browser_close_session",
        description="Close an existing browser session.",
        structured_output=True,
    )
    @log_mcp_tool("browser_close_session", settings.logging)
    async def browser_close_session(session_id: str) -> dict[str, Any]:
        return await session_manager.close_session(session_id)

    @mcp.tool(
        name="browser_save_session_state",
        description="Save the storage state (cookies, localStorage) of an active session to disk.",
        structured_output=True,
    )
    @log_mcp_tool("browser_save_session_state", settings.logging)
    async def browser_save_session_state(
        session_id: str,
        state_name: str,
    ) -> dict[str, Any]:
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", state_name):
            raise ValueError(
                "Invalid state_name. Use only letters, numbers, underscores, and hyphens."
            )

        settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        dest_path = settings.sessions_dir / f"{state_name}.json"

        await session_manager.save_storage_state(session_id, str(dest_path))
        return {
            "session_id": session_id,
            "state_name": state_name,
            "saved_path": str(dest_path),
            "success": True,
        }

    @mcp.tool(
        name="browser_screenshot_url",
        description=(
            "Capture a high-quality visual screenshot of a given URL. "
            "Supports rendering either a specific height or full scrollable height."
        ),
    )
    @log_mcp_tool("browser_screenshot_url", settings.logging)
    async def browser_screenshot_url(
        url: str,
        width: int = 1200,
        height: int | None = None,
        session_id: str | None = None,
    ) -> list[Any]:
        """Capture a visual screen snapshot of any webpage.

        Args:
            url: The target page URL to capture.
            width: Viewport width in pixels. Defaults to 1200.
            height: Viewport height in pixels. If None, auto-scrolls to capture the full page.
            session_id: Optional reusable session ID to execute the capture in
                (for logged-in states).
        """
        import base64
        from uuid import uuid4

        from mcp.types import ImageContent, TextContent

        is_temp_session = False
        active_session_id = session_id

        if not active_session_id:
            session_info = await session_manager.create_session(headless=True)
            active_session_id = session_info.session_id
            is_temp_session = True

        try:
            page = await session_manager.get_page(active_session_id)

            initial_height = height if height is not None else 800
            await page.set_viewport_size({"width": width, "height": initial_height})

            await page.goto(
                url, wait_until="load", timeout=settings.browser_search.browser.timeout_ms
            )
            try:
                await page.wait_for_load_state(
                    "networkidle", timeout=settings.browser_search.browser.timeout_ms
                )
            except Exception:
                # Networkidle timeout can be ignored if page is otherwise loaded
                pass

            if height is None:
                content_height = await page.evaluate("() => document.documentElement.scrollHeight")
                viewport_height = max(content_height, 1)
                await page.set_viewport_size({"width": width, "height": viewport_height})
                screenshot_bytes = await page.screenshot(full_page=False, type="png")
                actual_height = viewport_height
            else:
                screenshot_bytes = await page.screenshot(full_page=True, type="png")
                actual_height = height

        finally:
            if is_temp_session:
                await session_manager.close_session(active_session_id)

        output_dir = settings.render_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        resolved_path = output_dir / f"screenshot_{uuid4().hex[:8]}.png"

        import asyncio

        await asyncio.to_thread(resolved_path.write_bytes, screenshot_bytes)

        base64_data = base64.b64encode(screenshot_bytes).decode("utf-8")

        description = (
            f"Screenshot of {url} captured successfully.\n"
            f"Dimensions: {width}x{actual_height}px\n"
            f"Resource URI: render://{resolved_path.name}"
        )

        return [
            TextContent(type="text", text=description),
            ImageContent(
                type="image",
                data=base64_data,
                mimeType="image/png",
            ),
        ]
