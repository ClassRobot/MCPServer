"""Tests for low-level browser session lifecycle and extraction helpers."""

from __future__ import annotations

import pytest

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import BrowserSettings


class FakePage:
    """Minimal fake Playwright page object."""

    def __init__(self) -> None:
        self.url = "about:blank"
        self._title = "Blank"
        self._html = "<html><body></body></html>"
        self.filled: dict[str, str] = {}

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.url = url
        self._title = "Example Page"
        self._html = """
        <html>
          <body>
            <main>
              <h1>Example Page</h1>
              <p>Hello from the browser session.</p>
              <a href=\"https://example.com/docs\">Docs</a>
              <a href=\"/relative-path\">Relative</a>
            </main>
          </body>
        </html>
        """

    async def title(self) -> str:
        return self._title

    async def fill(self, selector: str, value: str, timeout: int) -> None:
        self.filled[selector] = value

    async def click(self, selector: str, timeout: int) -> None:
        self.url = f"{self.url}#clicked"

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        return None

    async def content(self) -> str:
        return self._html


class FakeContext:
    """Minimal fake browser context."""

    def __init__(self, page: FakePage) -> None:
        self._page = page
        self.closed = False

    async def new_page(self) -> FakePage:
        return self._page

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    """Minimal fake browser handle."""

    def __init__(self, context: FakeContext) -> None:
        self._context = context
        self.closed = False

    async def new_context(self, **kwargs) -> FakeContext:
        return self._context

    async def close(self) -> None:
        self.closed = True


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
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


@pytest.mark.asyncio
async def test_browser_session_manager_open_fill_click_extract_and_close() -> None:
    manager = BrowserSessionManager(BrowserSettings())
    fake_page = FakePage()
    fake_context = FakeContext(fake_page)
    fake_browser = FakeBrowser(fake_context)
    fake_playwright = FakePlaywright(FakeChromium(fake_browser))
    manager._playwright = fake_playwright

    session = await manager.create_session()
    opened = await manager.open(session.session_id, "https://example.com/")
    filled = await manager.fill(session.session_id, "#search", "openai")
    clicked = await manager.click(session.session_id, "#submit")
    extracted = await manager.extract(session.session_id, selector="main", include_links=True)
    closed = await manager.close_session(session.session_id)

    assert opened["title"] == "Example Page"
    assert filled["value"] == "openai"
    assert clicked["url"].endswith("#clicked")
    assert "Hello from the browser session." in extracted.text
    assert extracted.links[0].url == "https://example.com/docs"
    assert extracted.links[1].url == "https://example.com/relative-path"
    assert closed["closed"] is True
