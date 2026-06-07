"""MCP tools for Microsoft MarkItDown document-to-Markdown conversion."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.markitdown import MarkItDownConversionService
from mcp_server.tool_logging import log_mcp_tool


def register_markitdown_tools(
    mcp: FastMCP,
    *,
    markitdown_service: MarkItDownConversionService,
    logging_settings: LoggingSettings,
) -> None:
    """Register MarkItDown conversion tools on a FastMCP server."""

    @mcp.tool(
        name="convert_to_markdown",
        description=(
            "Convert a whitelisted local file or file:// URI to Markdown using "
            "Microsoft MarkItDown."
        ),
        structured_output=True,
    )
    @log_mcp_tool("convert_to_markdown", logging_settings)
    async def convert_to_markdown(uri: str, save_output: bool | None = None) -> dict[str, Any]:
        """Convert a local file to Markdown and optionally persist the generated Markdown."""
        result = await markitdown_service.convert_to_markdown(
            uri,
            save_output=save_output,
        )
        return asdict(result)
