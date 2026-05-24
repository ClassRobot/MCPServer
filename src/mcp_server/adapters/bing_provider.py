"""Bing page adapter for browser-driven search."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import BrowserSettings
from mcp_server.schemas import RawSearchResult


class BingSearchProvider:
    """Extract candidate search results from Bing result pages."""

    def __init__(self, settings: BrowserSettings) -> None:
        self._settings = settings

    def build_search_url(self, query: str) -> str:
        """Build the Bing URL for a text query."""
        return f"https://www.bing.com/search?q={quote_plus(query)}"

    async def search(
        self,
        session_manager: BrowserSessionManager,
        session_id: str,
        query: str,
    ) -> list[RawSearchResult]:
        """Run a Bing search inside an existing browser session."""
        page = await session_manager.get_page(session_id)
        await page.goto(
            self.build_search_url(query),
            wait_until="domcontentloaded",
            timeout=self._settings.timeout_ms,
        )
        try:
            await page.wait_for_selector(
                "#b_results",
                state="attached",
                timeout=self._settings.timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Bing result container '#b_results' was not attached.") from exc
        html = await page.content()
        return self.parse_results(html)

    def parse_results(self, html: str) -> list[RawSearchResult]:
        """Parse Bing HTML into raw candidate results for later filtering."""
        soup = BeautifulSoup(html, "html.parser")
        results_root = soup.select_one("#b_results")
        if results_root is None:
            return []

        parsed_results: list[RawSearchResult] = []
        for candidate in self._iter_candidates(results_root):
            classes = set(candidate.get("class", []))
            anchor = candidate.select_one("h2 a[href]") or candidate.select_one("a[href]")
            title = anchor.get_text(" ", strip=True) if anchor is not None else ""
            url = anchor.get("href", "").strip() if anchor is not None else ""
            snippet_node = candidate.select_one(".b_caption p") or candidate.select_one("p")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node is not None else None
            source = self._infer_source(url)
            is_natural = "b_algo" in classes
            is_ad = self._looks_like_ad(candidate, classes)

            parsed_results.append(
                RawSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet or None,
                    source=source,
                    is_ad=is_ad,
                    is_natural=is_natural,
                )
            )
        return parsed_results

    def _iter_candidates(self, results_root: Tag) -> Iterable[Tag]:
        """Iterate over top-level candidate nodes from the Bing result container."""
        for child in results_root.find_all(["li", "div"], recursive=False):
            if not isinstance(child, Tag):
                continue
            classes = set(child.get("class", []))
            if classes & {"b_pag", "b_ans"}:
                continue
            if child.select_one("a[href]") is None:
                continue
            yield child

    def _looks_like_ad(self, candidate: Tag, classes: set[str]) -> bool:
        """Detect obvious ad or sponsored result blocks."""
        if classes & {"b_ad", "ads", "sponsored"}:
            return True

        marker_selectors = [
            ".b_adLabel",
            ".ads_label",
            ".sponsored",
            "[aria-label='Ad']",
        ]
        if any(candidate.select_one(selector) is not None for selector in marker_selectors):
            return True

        marker_text = " ".join(
            marker.get_text(" ", strip=True)
            for marker in candidate.select(".b_adLabel, .ads_label, .sponsored, .label")
        ).lower()
        return any(token in marker_text for token in {"ad", "ads", "sponsored"})

    def _infer_source(self, url: str) -> str:
        """Infer a source label from the target URL."""
        parsed = urlparse(url)
        return parsed.netloc or "bing"
