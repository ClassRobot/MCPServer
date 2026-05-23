"""Service exports for browser-driven search."""

from .browser_search import BrowserSearchService
from .search_results import SearchResultFilter

__all__ = ["BrowserSearchService", "SearchResultFilter"]
