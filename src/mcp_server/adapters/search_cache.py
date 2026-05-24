"""Filesystem-backed cache for structured browser search results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mcp_server.config import SearchCacheSettings
from mcp_server.schemas import BrowserSearchResponse, SearchResult


class SearchCacheStore:
    """Store structured search responses in a bounded JSON file cache."""

    def __init__(self, settings: SearchCacheSettings) -> None:
        self._settings = settings

    def build_cache_key(
        self,
        *,
        provider: str,
        normalized_query: str,
        max_results: int,
        filter_ads: bool,
        include_summary: bool,
    ) -> str:
        """Build a stable cache key for a high-level browser search request."""
        payload = json.dumps(
            {
                "provider": provider,
                "query": normalized_query,
                "max_results": max_results,
                "filter_ads": filter_ads,
                "include_summary": include_summary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> BrowserSearchResponse | None:
        """Return a cached search response when it exists and is still fresh."""
        if not self._settings.enabled:
            return None

        cache_file = self._cache_file(cache_key)
        if not cache_file.exists():
            return None

        try:
            with cache_file.open("r", encoding="utf-8") as cache_handle:
                payload = json.load(cache_handle)
        except (OSError, json.JSONDecodeError):
            cache_file.unlink(missing_ok=True)
            return None

        expires_at = datetime.fromisoformat(payload["expires_at"])
        if expires_at <= datetime.now(UTC):
            cache_file.unlink(missing_ok=True)
            return None

        response_payload = payload["response"]
        return BrowserSearchResponse(
            query=response_payload["query"],
            provider=response_payload["provider"],
            summary=response_payload["summary"],
            cache_hit=True,
            filtered_count=response_payload["filtered_count"],
            results=[
                SearchResult(
                    rank=result["rank"],
                    title=result["title"],
                    url=result["url"],
                    snippet=result["snippet"],
                    source=result["source"],
                )
                for result in response_payload["results"]
            ],
        )

    def set(self, cache_key: str, response: BrowserSearchResponse) -> None:
        """Persist a structured search response in the cache."""
        if not self._settings.enabled:
            return

        cache_file = self._cache_file(cache_key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (
                datetime.now(UTC) + timedelta(seconds=self._settings.ttl_sec)
            ).isoformat(),
            "response": asdict(response),
        }
        with cache_file.open("w", encoding="utf-8") as cache_handle:
            json.dump(payload, cache_handle, ensure_ascii=False, indent=2)
        self.prune()

    def prune(self) -> None:
        """Delete expired or excessive cache entries using fast filesystem metadata checks.

        NOTE ON EXPIRATION STRATEGY:
        For performance reasons, prune() uses `st_mtime` and the current `ttl_sec` setting
        to clean up expired files without loading and parsing every JSON file on disk.
        Conversely, get() uses the explicit `expires_at` timestamp written inside the JSON payload.
        While changing `ttl_sec` dynamically might create a slight temporary discrepancy between
        the two methods, this trade-off is intentional to keep prune() extremely fast (O(N) stat
        calls instead of O(N) file reads and JSON parses).
        """
        cache_dir = self._settings.base_dir
        if not cache_dir.exists():
            return

        now_ts = datetime.now(UTC).timestamp()
        ttl = self._settings.ttl_sec

        try:
            cache_files = list(cache_dir.glob("*.json"))
        except OSError:
            return

        valid_files: list[tuple[float, Path]] = []
        for cache_file in cache_files:
            try:
                stat = cache_file.stat()
                # If the file modification time is older than current time minus TTL, it has expired
                if now_ts - stat.st_mtime > ttl:
                    cache_file.unlink(missing_ok=True)
                else:
                    valid_files.append((stat.st_mtime, cache_file))
            except OSError:
                continue

        # If still exceeding max_entries, sort by modification time and delete the oldest ones
        if len(valid_files) > self._settings.max_entries:
            valid_files.sort(key=lambda item: item[0], reverse=True)
            for _, extra_file in valid_files[self._settings.max_entries :]:
                extra_file.unlink(missing_ok=True)

    def _cache_file(self, cache_key: str) -> Path:
        """Return the file path used to store a cache entry."""
        return self._settings.base_dir / f"{cache_key}.json"
