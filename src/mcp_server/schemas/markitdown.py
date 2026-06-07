"""Structured outputs for Microsoft MarkItDown conversion tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MarkItDownConversionResult:
    """A Markdown conversion result returned by the MarkItDown MCP tool."""

    source_name: str
    source_uri: str
    markdown: str
    output_resource_uri: str | None
    input_bytes: int
    output_bytes: int
    converter: str = "markitdown"
