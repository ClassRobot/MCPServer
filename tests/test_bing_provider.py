"""Tests for Bing provider parsing and ad candidate detection."""

from pathlib import Path

from mcp_server.adapters.bing_provider import BingSearchProvider
from mcp_server.config import BrowserSettings

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_results_extracts_natural_bing_results() -> None:
    provider = BingSearchProvider(BrowserSettings())

    results = provider.parse_results(_read_fixture("bing_results.html"))

    assert len(results) == 2
    assert results[0].title == "OpenAI"
    assert results[0].is_natural is True
    assert results[0].is_ad is False


def test_parse_results_marks_ad_candidates() -> None:
    provider = BingSearchProvider(BrowserSettings())

    results = provider.parse_results(_read_fixture("bing_ads.html"))

    assert any(result.is_ad for result in results)
    assert any(result.url == "https://openai.com/" for result in results)


def test_parse_results_handles_empty_result_pages() -> None:
    provider = BingSearchProvider(BrowserSettings())

    results = provider.parse_results(_read_fixture("bing_empty.html"))

    assert results == []
