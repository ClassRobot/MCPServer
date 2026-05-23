"""Tests for the filesystem-backed browser search cache."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from mcp_server.adapters.search_cache import SearchCacheStore
from mcp_server.config import SearchCacheSettings
from mcp_server.schemas import BrowserSearchResponse, SearchResult


def _build_response() -> BrowserSearchResponse:
    return BrowserSearchResponse(
        query="openai",
        provider="bing",
        results=[
            SearchResult(
                rank=1,
                title="OpenAI",
                url="https://openai.com/",
                snippet="A result",
                source="openai.com",
            )
        ],
        summary="Top search results:\n1. OpenAI: A result",
        cache_hit=False,
        filtered_count=1,
    )


def test_cache_store_round_trip_marks_cache_hit(tmp_path) -> None:
    cache_store = SearchCacheStore(
        SearchCacheSettings(enabled=True, ttl_sec=1800, base_dir=tmp_path, max_entries=10)
    )
    cache_key = cache_store.build_cache_key(
        provider="bing",
        normalized_query="openai",
        max_results=5,
        filter_ads=True,
        include_summary=False,
    )

    cache_store.set(cache_key, _build_response())
    cached_response = cache_store.get(cache_key)

    assert cached_response is not None
    assert cached_response.cache_hit is True
    assert cached_response.results[0].title == "OpenAI"


def test_cache_store_discards_expired_entries(tmp_path) -> None:
    cache_store = SearchCacheStore(
        SearchCacheSettings(enabled=True, ttl_sec=1800, base_dir=tmp_path, max_entries=10)
    )
    cache_key = "expired"
    cache_store.set(cache_key, _build_response())
    cache_file = tmp_path / "expired.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    cached_response = cache_store.get(cache_key)

    assert cached_response is None
    assert not cache_file.exists()


def test_cache_store_prunes_exceeding_max_entries(tmp_path) -> None:
    cache_store = SearchCacheStore(
        SearchCacheSettings(enabled=True, ttl_sec=1800, base_dir=tmp_path, max_entries=2)
    )
    import time

    cache_store.set("key1", _build_response())
    time.sleep(0.01)
    cache_store.set("key2", _build_response())
    time.sleep(0.01)
    cache_store.set("key3", _build_response())

    assert not (tmp_path / "key1.json").exists()
    assert (tmp_path / "key2.json").exists()
    assert (tmp_path / "key3.json").exists()
