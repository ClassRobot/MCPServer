"""Shared schemas for browser-driven search and low-level browser tools."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchResult:
    """A structured natural search result returned to MCP clients."""

    rank: int
    title: str
    url: str
    snippet: str | None
    source: str


@dataclass(slots=True)
class BrowserSearchResponse:
    """The structured output returned by the high-level browser search tool."""

    query: str
    provider: str
    results: list[SearchResult]
    summary: str | None
    cache_hit: bool
    filtered_count: int


@dataclass(slots=True)
class BrowserSessionInfo:
    """Session metadata returned by low-level browser session tools."""

    session_id: str
    headless: bool


@dataclass(slots=True)
class BrowserExtractLink:
    """A hyperlink extracted from a page or DOM fragment."""

    text: str
    url: str


@dataclass(slots=True)
class BrowserExtractResult:
    """Structured page extraction output for low-level browser tools."""

    session_id: str
    title: str
    url: str
    text: str
    links: list[BrowserExtractLink] = field(default_factory=list)


@dataclass(slots=True)
class RawSearchResult:
    """A provider candidate result before filtering and normalization."""

    title: str
    url: str
    snippet: str | None
    source: str
    is_ad: bool = False
    is_natural: bool = True
