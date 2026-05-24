"""Playwright-backed browser session management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin
from uuid import uuid4

from bs4 import BeautifulSoup
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from mcp_server.config import BrowserSettings
from mcp_server.schemas import (
    BrowserExtractLink,
    BrowserExtractResult,
    BrowserSessionInfo,
)


@dataclass(slots=True)
class ManagedBrowserSession:
    """Runtime state for a single browser session."""

    session_id: str
    browser: Browser
    context: BrowserContext
    page: Page
    headless: bool
    created_at: datetime
    last_used_at: datetime


class BrowserSessionManager:
    """Manage Playwright browser sessions shared by low-level browser tools."""

    def __init__(self, settings: BrowserSettings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._sessions: dict[str, ManagedBrowserSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, headless: bool | None = None) -> BrowserSessionInfo:
        """Create a new browser session and return its public metadata."""
        await self._cleanup_expired_sessions()
        playwright = await self._ensure_playwright()
        session_headless = self._settings.headless if headless is None else headless
        browser = await playwright.chromium.launch(headless=session_headless)
        try:
            context_kwargs: dict[str, Any] = {}
            if self._settings.user_agent is not None:
                context_kwargs["user_agent"] = self._settings.user_agent
            context = await browser.new_context(**context_kwargs)
            try:
                page = await context.new_page()
            except Exception:
                await context.close()
                raise
        except Exception:
            await browser.close()
            raise

        session_id = uuid4().hex
        timestamp = datetime.now(UTC)
        self._sessions[session_id] = ManagedBrowserSession(
            session_id=session_id,
            browser=browser,
            context=context,
            page=page,
            headless=session_headless,
            created_at=timestamp,
            last_used_at=timestamp,
        )
        return BrowserSessionInfo(session_id=session_id, headless=session_headless)

    async def open(self, session_id: str, url: str) -> dict[str, str]:
        """Open a URL in the given session and return the resulting page identity."""
        page = await self.get_page(session_id)
        try:
            await page.goto(url, wait_until="load", timeout=self._settings.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Timed out while opening {url!r}.") from exc
        except PlaywrightError as exc:
            raise RuntimeError(f"Failed to open {url!r}: {exc}") from exc
        return {
            "session_id": session_id,
            "url": page.url,
            "title": await page.title(),
        }

    async def fill(
        self, session_id: str, selector: str, value: str, clear: bool = True
    ) -> dict[str, str]:
        """Fill an input field in the given session."""
        page = await self.get_page(session_id)
        try:
            if clear:
                await page.fill(selector, "", timeout=self._settings.timeout_ms)
            await page.fill(selector, value, timeout=self._settings.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Timed out while filling selector {selector!r}.") from exc
        except PlaywrightError as exc:
            raise RuntimeError(f"Failed to fill selector {selector!r}: {exc}") from exc
        return {
            "session_id": session_id,
            "selector": selector,
            "value": value,
        }

    async def click(
        self,
        session_id: str,
        selector: str,
        wait_for_network_idle: bool = True,
    ) -> dict[str, str]:
        """Click a page element in the given session."""
        page = await self.get_page(session_id)
        try:
            await page.click(selector, timeout=self._settings.timeout_ms)
            if wait_for_network_idle:
                await page.wait_for_load_state("networkidle", timeout=self._settings.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Timed out while clicking selector {selector!r}.") from exc
        except PlaywrightError as exc:
            raise RuntimeError(f"Failed to click selector {selector!r}: {exc}") from exc
        return {
            "session_id": session_id,
            "url": page.url,
            "title": await page.title(),
        }

    async def extract(
        self,
        session_id: str,
        selector: str | None = None,
        include_links: bool = False,
        max_links: int = 10,
    ) -> BrowserExtractResult:
        """Extract page text and optional links from the current session page."""
        page = await self.get_page(session_id)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        scope = soup.select_one(selector) if selector else soup
        text = scope.get_text(" ", strip=True) if scope is not None else ""

        links: list[BrowserExtractLink] = []
        if include_links and scope is not None:
            for link in scope.select("a[href]")[:max_links]:
                href = link.get("href", "").strip()
                if not href:
                    continue
                links.append(
                    BrowserExtractLink(
                        text=link.get_text(" ", strip=True),
                        url=urljoin(page.url, href),
                    )
                )

        return BrowserExtractResult(
            session_id=session_id,
            title=await page.title(),
            url=page.url,
            text=text,
            links=links,
        )

    async def get_page(self, session_id: str) -> Page:
        """Fetch the current page for a live session and refresh its TTL."""
        await self._cleanup_expired_sessions()
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"Browser session {session_id!r} does not exist or has expired.")
        session.last_used_at = datetime.now(UTC)
        return session.page

    async def close_session(self, session_id: str) -> dict[str, bool | str]:
        """Close a single browser session."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return {"session_id": session_id, "closed": False}

        await session.context.close()
        await session.browser.close()
        return {"session_id": session_id, "closed": True}

    async def close_all(self) -> None:
        """Close all live sessions and stop Playwright."""
        session_ids = list(self._sessions)
        for session_id in session_ids:
            try:
                await self.close_session(session_id)
            except Exception:
                pass

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            finally:
                self._playwright = None

    async def _ensure_playwright(self) -> Playwright:
        """Start Playwright lazily when the first session is needed."""
        async with self._lock:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            return self._playwright

    async def _cleanup_expired_sessions(self) -> None:
        """Close sessions whose TTL has elapsed."""
        async with self._lock:
            expiration_cutoff = datetime.now(UTC) - timedelta(seconds=self._settings.session_ttl_sec)
            expired_ids = [
                session_id
                for session_id, session in self._sessions.items()
                if session.last_used_at < expiration_cutoff
            ]
            for session_id in expired_ids:
                await self.close_session(session_id)
