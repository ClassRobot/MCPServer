"""Tests for Baidu provider parsing and ad candidate detection."""

from pathlib import Path

import pytest

from mcp_server.adapters.baidu_provider import BaiduSearchProvider
from mcp_server.config import BrowserSettings

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_results_extracts_natural_baidu_results() -> None:
    provider = BaiduSearchProvider(BrowserSettings())

    results = provider.parse_results(_read_fixture("baidu_results.html"))

    assert len(results) == 2
    assert results[0].title == "百度一下，你就知道"
    assert results[0].is_natural is True
    assert results[0].is_ad is False
    assert results[0].snippet == "全球领先的中文搜索引擎、致力于让网民更便捷地获取信息，找到所求。"

    assert results[1].title == "OpenAI"
    assert results[1].is_natural is True
    assert results[1].is_ad is False
    assert results[1].snippet == "OpenAI is an AI research and deployment company."


def test_parse_results_marks_ad_candidates() -> None:
    provider = BaiduSearchProvider(BrowserSettings())

    results = provider.parse_results(_read_fixture("baidu_ads.html"))

    assert len(results) == 1
    assert results[0].is_ad is True
    assert results[0].is_natural is False
    assert results[0].title == "极速贷款，秒批到账"


def test_parse_results_handles_empty_result_pages() -> None:
    provider = BaiduSearchProvider(BrowserSettings())

    results = provider.parse_results(_read_fixture("baidu_empty.html"))

    assert results == []


@pytest.mark.asyncio
async def test_baidu_search_waits_for_attached_results_container() -> None:
    provider = BaiduSearchProvider(BrowserSettings())
    page = _FakePage(_read_fixture("baidu_results.html"))

    results = await provider.search(
        session_manager=_FakeSessionManager(page),
        session_id="test-session",
        query="baidu",
    )

    assert results
    assert page.wait_selector == "#content_left"
    assert page.wait_state == "attached"


class _FakeSessionManager:
    def __init__(self, page: "_FakePage") -> None:
        self._page = page

    async def get_page(self, session_id: str) -> "_FakePage":
        assert session_id == "test-session"
        return self._page


class _FakePage:
    def __init__(self, html: str) -> None:
        self._html = html
        self.wait_selector: str | None = None
        self.wait_state: str | None = None

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        assert "baidu.com/s" in url
        assert wait_until == "domcontentloaded"
        assert timeout > 0

    async def wait_for_selector(self, selector: str, *, state: str, timeout: int) -> None:
        self.wait_selector = selector
        self.wait_state = state
        assert timeout > 0

    async def content(self) -> str:
        return self._html
