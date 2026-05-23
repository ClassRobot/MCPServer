"""High-level browser search orchestration."""

from __future__ import annotations

import asyncio
from typing import Protocol

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.adapters.search_cache import SearchCacheStore
from mcp_server.config import BrowserSettings, SearchCacheSettings
from mcp_server.schemas import BrowserSearchResponse, RawSearchResult, SearchResult
from mcp_server.services.search_results import SearchResultFilter


class BrowserSearchProvider(Protocol):
    """Provider contract for browser-driven search backends."""

    async def search(
        self,
        session_manager: BrowserSessionManager,
        session_id: str,
        query: str,
    ) -> list[RawSearchResult]:
        """Return raw provider candidates for a given query."""


class BrowserSearchService:
    """Coordinate provider access, filtering, summaries, and cache behavior."""

    def __init__(
        self,
        *,
        session_manager: BrowserSessionManager,
        cache_store: SearchCacheStore,
        providers: dict[str, BrowserSearchProvider],
        result_filter: SearchResultFilter,
        browser_settings: BrowserSettings,
        cache_settings: SearchCacheSettings,
    ) -> None:
        self._session_manager = session_manager
        self._cache_store = cache_store
        self._providers = providers
        self._result_filter = result_filter
        self._browser_settings = browser_settings
        self._cache_settings = cache_settings

    async def search(
        self,
        *,
        query: str,
        provider: str = "bing",
        max_results: int | None = None,
        include_summary: bool = False,
        use_cache: bool = True,
        force_refresh: bool = False,
        filter_ads: bool = True,
    ) -> BrowserSearchResponse:
        """Run a high-level browser search and return structured results."""
        normalized_query = self._normalize_query(query)
        resolved_provider = provider or self._browser_settings.default_provider
        provider_impl = self._providers.get(resolved_provider)
        if provider_impl is None:
            raise RuntimeError(f"Unsupported search provider: {resolved_provider!r}.")

        limit = max_results or self._browser_settings.max_results
        if limit <= 0:
            raise ValueError("max_results must be a positive integer.")

        cache_key = self._cache_store.build_cache_key(
            provider=resolved_provider,
            normalized_query=normalized_query,
            max_results=limit,
            filter_ads=filter_ads,
            include_summary=include_summary,
        )

        if use_cache and self._cache_settings.enabled and not force_refresh:
            cached_response = self._cache_store.get(cache_key)
            if cached_response is not None:
                return cached_response

        session_info = await self._session_manager.create_session()
        try:
            raw_results = await provider_impl.search(
                self._session_manager,
                session_info.session_id,
                normalized_query,
            )
        finally:
            await self._session_manager.close_session(session_info.session_id)

        filtered_results, filtered_count = self._result_filter.filter_results(
            raw_results,
            filter_ads=filter_ads,
        )
        limited_results = self._apply_limit(filtered_results, limit)
        summary = self._build_summary(limited_results) if include_summary else None

        response = BrowserSearchResponse(
            query=normalized_query,
            provider=resolved_provider,
            results=limited_results,
            summary=summary,
            cache_hit=False,
            filtered_count=filtered_count,
        )

        if use_cache and self._cache_settings.enabled:
            await asyncio.to_thread(self._cache_store.set, cache_key, response)
        return response

    def _normalize_query(self, query: str) -> str:
        """Normalize search queries so cache keys and provider requests stay stable."""
        normalized = " ".join(query.split()).strip()
        if not normalized:
            raise ValueError("query must not be empty.")
        return normalized

    def _apply_limit(self, results: list[SearchResult], limit: int) -> list[SearchResult]:
        """Limit result count while preserving clean ranks."""
        limited = results[:limit]
        for index, result in enumerate(limited, start=1):
            result.rank = index
        return limited

    def _build_summary(self, results: list[SearchResult]) -> str | None:
        """Generate a lightweight summary from the top structured search results."""
        if not results:
            return None

        summary_lines = []
        for result in results[:3]:
            if result.snippet:
                summary_lines.append(f"{result.rank}. {result.title}: {result.snippet}")
            else:
                summary_lines.append(f"{result.rank}. {result.title}")
        return "Top search results:\n" + "\n".join(summary_lines)
