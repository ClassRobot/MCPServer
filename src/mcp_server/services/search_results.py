"""Filtering and normalization for raw browser search candidates."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from mcp_server.config import SearchFilterSettings
from mcp_server.schemas import RawSearchResult, SearchResult


class SearchResultFilter:
    """Apply ad filtering, validation, de-duplication, and ranking."""

    def __init__(self, settings: SearchFilterSettings) -> None:
        self._settings = settings

    def filter_results(
        self,
        raw_results: list[RawSearchResult],
        *,
        filter_ads: bool,
        strict_natural_results_only: bool | None = None,
    ) -> tuple[list[SearchResult], int]:
        """Transform raw provider candidates into stable structured search results."""
        strict_mode = (
            self._settings.strict_natural_results_only
            if strict_natural_results_only is None
            else strict_natural_results_only
        )
        filtered_count = 0
        seen_urls: set[str] = set()
        structured_results: list[SearchResult] = []

        for raw_result in raw_results:
            normalized_url = self._normalize_url(raw_result.url)
            if filter_ads and self._settings.ads_enabled and raw_result.is_ad:
                filtered_count += 1
                continue
            if strict_mode and not raw_result.is_natural:
                filtered_count += 1
                continue
            if not raw_result.title.strip() or not normalized_url:
                filtered_count += 1
                continue
            if normalized_url in seen_urls:
                filtered_count += 1
                continue

            seen_urls.add(normalized_url)
            structured_results.append(
                SearchResult(
                    rank=len(structured_results) + 1,
                    title=raw_result.title.strip(),
                    url=normalized_url,
                    snippet=raw_result.snippet.strip() if raw_result.snippet else None,
                    source=raw_result.source,
                )
            )

        return structured_results, filtered_count

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL enough to support stable de-duplication."""
        if not url:
            return ""

        parsed = urlparse(url.strip())
        if not parsed.netloc:
            return ""

        cleaned_query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if key.lower()
                not in {"utm_source", "utm_medium", "utm_campaign", "gclid", "fbclid"}
            ]
        )
        normalized = parsed._replace(
            scheme=(parsed.scheme or "https").lower(),
            netloc=parsed.netloc.lower(),
            query=cleaned_query,
            fragment="",
        )
        return urlunparse(normalized)
