"""Tests for high-level browser search orchestration and cache behavior."""

from __future__ import annotations

import asyncio

from mcp_server.adapters.search_cache import SearchCacheStore
from mcp_server.config import BrowserSettings, SearchCacheSettings, SearchFilterSettings
from mcp_server.schemas import BrowserSessionInfo, RawSearchResult
from mcp_server.services.browser_search import BrowserSearchService
from mcp_server.services.search_results import SearchResultFilter


class FakeSessionManager:
    """Minimal session manager used to unit test high-level search orchestration."""

    def __init__(self) -> None:
        self.created_sessions: list[str] = []
        self.closed_sessions: list[str] = []
        self._next_session = 0

    async def create_session(self, headless: bool | None = None) -> BrowserSessionInfo:
        self._next_session += 1
        session_id = f"session-{self._next_session}"
        self.created_sessions.append(session_id)
        return BrowserSessionInfo(session_id=session_id, headless=True)

    async def close_session(self, session_id: str) -> dict[str, bool | str]:
        self.closed_sessions.append(session_id)
        return {"session_id": session_id, "closed": True}


class FakeProvider:
    """Provider stub used to verify cache behavior and result processing."""

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, session_manager, session_id: str, query: str) -> list[RawSearchResult]:
        self.calls += 1
        return [
            RawSearchResult(
                title="Sponsored Listing",
                url="https://ads.example.com/",
                snippet="Ad result",
                source="ads.example.com",
                is_ad=True,
                is_natural=False,
            ),
            RawSearchResult(
                title="OpenAI",
                url="https://openai.com/",
                snippet="OpenAI homepage",
                source="openai.com",
            ),
        ]


def test_browser_search_service_uses_cache_and_filters_ads(tmp_path) -> None:
    session_manager = FakeSessionManager()
    provider = FakeProvider()
    service = BrowserSearchService(
        session_manager=session_manager,
        cache_store=SearchCacheStore(
            SearchCacheSettings(enabled=True, ttl_sec=1800, base_dir=tmp_path, max_entries=10)
        ),
        providers={"bing": provider},
        result_filter=SearchResultFilter(SearchFilterSettings()),
        browser_settings=BrowserSettings(),
        cache_settings=SearchCacheSettings(
            enabled=True, ttl_sec=1800, base_dir=tmp_path, max_entries=10
        ),
    )

    first_response = asyncio.run(service.search(query="openai", include_summary=True))
    second_response = asyncio.run(service.search(query="openai", include_summary=True))

    assert provider.calls == 1
    assert first_response.cache_hit is False
    assert second_response.cache_hit is True
    assert first_response.filtered_count == 1
    assert first_response.results[0].title == "OpenAI"
    assert first_response.summary is not None
    assert session_manager.created_sessions == ["session-1"]
    assert session_manager.closed_sessions == ["session-1"]


def test_browser_search_service_force_refresh_bypasses_cache(tmp_path) -> None:
    session_manager = FakeSessionManager()
    provider = FakeProvider()
    cache_settings = SearchCacheSettings(
        enabled=True, ttl_sec=1800, base_dir=tmp_path, max_entries=10
    )
    service = BrowserSearchService(
        session_manager=session_manager,
        cache_store=SearchCacheStore(cache_settings),
        providers={"bing": provider},
        result_filter=SearchResultFilter(SearchFilterSettings()),
        browser_settings=BrowserSettings(),
        cache_settings=cache_settings,
    )

    asyncio.run(service.search(query="openai"))
    asyncio.run(service.search(query="openai", force_refresh=True))

    assert provider.calls == 2
