"""Tests for search result filtering, de-duplication, and normalization."""

from mcp_server.config import SearchFilterSettings
from mcp_server.schemas import RawSearchResult
from mcp_server.services.search_results import SearchResultFilter


def test_filter_results_removes_ads_duplicates_and_invalid_entries() -> None:
    result_filter = SearchResultFilter(SearchFilterSettings())
    raw_results = [
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
            url="https://openai.com/?utm_source=bing",
            snippet="Primary result",
            source="openai.com",
        ),
        RawSearchResult(
            title="OpenAI Duplicate",
            url="https://openai.com/",
            snippet="Duplicate result",
            source="openai.com",
        ),
        RawSearchResult(
            title="",
            url="https://invalid.example.com/",
            snippet="Missing title",
            source="invalid.example.com",
        ),
    ]

    results, filtered_count = result_filter.filter_results(raw_results, filter_ads=True)

    assert len(results) == 1
    assert results[0].url == "https://openai.com/"
    assert filtered_count == 3


def test_filter_results_can_keep_non_ad_non_natural_candidates() -> None:
    result_filter = SearchResultFilter(SearchFilterSettings(strict_natural_results_only=False))
    raw_results = [
        RawSearchResult(
            title="Knowledge Card",
            url="https://example.com/card",
            snippet=None,
            source="example.com",
            is_ad=False,
            is_natural=False,
        )
    ]

    results, filtered_count = result_filter.filter_results(raw_results, filter_ads=True)

    assert len(results) == 1
    assert filtered_count == 0
