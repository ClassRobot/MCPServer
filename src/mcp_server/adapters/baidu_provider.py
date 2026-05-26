"""Baidu page adapter for browser-driven search."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import BrowserSettings
from mcp_server.schemas import RawSearchResult


class BaiduSearchProvider:
    """Extract candidate search results from Baidu search pages."""

    def __init__(self, settings: BrowserSettings) -> None:
        self._settings = settings

    def build_search_url(self, query: str) -> str:
        """Build the Baidu URL for a text query."""
        return f"https://www.baidu.com/s?wd={quote_plus(query)}"

    async def search(
        self,
        session_manager: BrowserSessionManager,
        session_id: str,
        query: str,
    ) -> list[RawSearchResult]:
        """Run a Baidu search inside an existing browser session."""
        page = await session_manager.get_page(session_id)
        
        await page.goto(
            self.build_search_url(query),
            wait_until="domcontentloaded",
            timeout=self._settings.timeout_ms,
        )
        
        try:
            # Wait for the main results container
            await page.wait_for_selector(
                "#content_left",
                state="attached",
                timeout=self._settings.timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Baidu result container '#content_left' was not attached.") from exc
            
        html = await page.content()
        return self.parse_results(html)

    def parse_results(self, html: str) -> list[RawSearchResult]:
        """Parse Baidu HTML into raw candidate results."""
        soup = BeautifulSoup(html, "html.parser")
        results_root = soup.select_one("#content_left")
        if results_root is None:
            return []

        parsed_results: list[RawSearchResult] = []
        for candidate in self._iter_candidates(results_root):
            classes = set(candidate.get("class", []))
            
            # Extract Title and URL
            title_node = candidate.select_one("h3") or candidate.select_one(".t")
            anchor = title_node.select_one("a[href]") if title_node else candidate.select_one("a[href]")
            
            title = anchor.get_text(" ", strip=True) if anchor else ""
            url = anchor.get("href", "").strip() if anchor else ""
            
            # Extract Snippet
            snippet_node = (
                candidate.select_one(".content-abstract") or 
                candidate.select_one(".c-abstract") or
                candidate.select_one(".c-span18") or
                candidate.select_one(".c-span-all")
            )
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None
            
            # Extract Site Name / Source
            source_node = candidate.select_one(".c-showurl") or candidate.select_one(".g")
            site_name = source_node.get_text(" ", strip=True) if source_node else None
            source = self._infer_source(url) if url else "baidu"

            is_ad = self._looks_like_ad(candidate, classes)
            is_natural = ("result" in classes or "result-op" in classes) and not is_ad

            parsed_results.append(
                RawSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source,
                    is_ad=is_ad,
                    is_natural=is_natural,
                )
            )
        return parsed_results

    def _iter_candidates(self, results_root: Tag) -> Iterable[Tag]:
        """Iterate over result nodes from Baidu's content_left."""
        for child in results_root.find_all("div", recursive=False):
            if not isinstance(child, Tag):
                continue
            if child.get("id") == "rs" or "hint" in child.get("class", []):
                continue
            yield child

    def _looks_like_ad(self, candidate: Tag, classes: set[str]) -> bool:
        """Detect Baidu ads (marked with '广告')."""
        ad_labels = candidate.select(".c-gray") + candidate.select("span")
        for label in ad_labels:
            if "广告" in label.get_text():
                return True
        if candidate.get("data-tu") or "m" in classes:
            return True
        return False

    def _infer_source(self, url: str) -> str:
        """Infer a source label from the URL."""
        if not url:
            return "baidu"
        try:
            parsed = urlparse(url)
            return parsed.netloc or "baidu"
        except Exception:
            return "baidu"
