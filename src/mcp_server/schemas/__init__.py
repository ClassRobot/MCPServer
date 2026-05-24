"""Shared schema exports for browser search and browser tools.

NOTE ON MUTABILITY:
Unlike configuration models, dataclasses in the schemas/ package are deliberately
defined WITHOUT `frozen=True` (only `slots=True`). This design decision is intentional
to allow in-place mutations (e.g., dynamic ranking adjustments of SearchResult).
Do not add `frozen=True` to schemas unless you are sure no components require mutability.
"""

from .browser import (
    BrowserExtractLink,
    BrowserExtractResult,
    BrowserSearchResponse,
    BrowserSessionInfo,
    RawSearchResult,
    SearchResult,
)
from .rendering import RenderImageResult

__all__ = [
    "BrowserExtractLink",
    "BrowserExtractResult",
    "BrowserSearchResponse",
    "BrowserSessionInfo",
    "RawSearchResult",
    "SearchResult",
    "RenderImageResult",
]
