"""Tests for HTML and Markdown to image rendering services and tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import BrowserSettings
from mcp_server.services.rendering import ContentRenderingService


class FakePage:
    """Minimal fake Playwright page object for rendering tests."""

    def __init__(self) -> None:
        self.viewport_size: dict[str, int] = {}
        self.html_content: str = ""
        self.load_states_waited: list[str] = []

    async def set_viewport_size(self, viewport_size: dict[str, int]) -> None:
        self.viewport_size = viewport_size

    async def set_content(self, html: str) -> None:
        self.html_content = html

    async def wait_for_load_state(self, state: str) -> None:
        self.load_states_waited.append(state)

    async def evaluate(self, script: str) -> int:
        return 450

    async def screenshot(self, full_page: bool, type: str) -> bytes:
        return b"fake_png_data"


class FakeContext:
    """Minimal fake browser context."""

    def __init__(self, page: FakePage) -> None:
        self._page = page

    async def new_page(self) -> FakePage:
        return self._page

    async def close(self) -> None:
        pass


class FakeBrowser:
    """Minimal fake browser handle."""

    def __init__(self, context: FakeContext) -> None:
        self._context = context

    async def new_context(self, **kwargs) -> FakeContext:
        return self._context

    async def close(self) -> None:
        pass


class FakeChromium:
    """Minimal fake browser launcher."""

    def __init__(self, browser: FakeBrowser) -> None:
        self._browser = browser

    async def launch(self, headless: bool) -> FakeBrowser:
        return self._browser


class FakePlaywright:
    """Minimal fake Playwright runtime."""

    def __init__(self, chromium: FakeChromium) -> None:
        self.chromium = chromium

    async def stop(self) -> None:
        pass


import pytest


@pytest.mark.asyncio
async def test_rendering_service_html_and_markdown(tmp_path: Path) -> None:
    # Setup session manager with fake playwright
    manager = BrowserSessionManager(BrowserSettings())
    fake_page = FakePage()
    fake_context = FakeContext(fake_page)
    fake_browser = FakeBrowser(fake_context)
    fake_playwright = FakePlaywright(FakeChromium(fake_browser))
    manager._playwright = fake_playwright

    service = ContentRenderingService(
        session_manager=manager,
        default_output_dir=tmp_path / "render",
    )

    # Test HTML rendering
    result_html = await service.render(
        content="<h1>Test HTML</h1>",
        input_format="html",
        width=1000,
        height=800,
        output_path="test_html.png",
    )

    assert Path(result_html.file_path).name == "test_html.png"
    assert result_html.width == 1000
    assert result_html.height == 800
    assert result_html.input_format == "html"
    assert result_html.base64_image == "ZmFrZV9wbmdfZGF0YQ=="  # base64 of b"fake_png_data"
    assert fake_page.viewport_size == {"width": 1000, "height": 800}
    assert fake_page.html_content == "<h1>Test HTML</h1>"

    # Test Markdown rendering with auto height (height=None)
    result_md = await service.render(
        content="# Title\nSome content.",
        input_format="markdown",
        theme="dark",
        width=800,
        height=None,
        output_path="test_md.png",
    )

    assert Path(result_md.file_path).name == "test_md.png"
    assert result_md.input_format == "markdown"
    assert result_md.height == 450  # Matches FakePage.evaluate mock content height
    assert "Title" in fake_page.html_content
    assert "Some content." in fake_page.html_content
    assert "#0d1117" in fake_page.html_content  # dark background color should be in style

