"""Tests for MarkItDown generated Markdown resource access."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server.resources.markitdown import register_markitdown_resources


@pytest.mark.asyncio
async def test_read_markitdown_resource_success(tmp_path: Path) -> None:
    mcp = FastMCP("test")
    register_markitdown_resources(mcp, tmp_path)
    (tmp_path / "sample.md").write_text("# Converted\n", encoding="utf-8")

    contents = await mcp.read_resource("markitdown://sample.md")

    assert len(contents) == 1
    assert contents[0].content == "# Converted\n"


@pytest.mark.asyncio
async def test_read_markitdown_resource_blocks_traversal(tmp_path: Path) -> None:
    mcp = FastMCP("test")
    register_markitdown_resources(mcp, tmp_path)

    with pytest.raises(ValueError, match="Directory traversal attempt detected."):
        await mcp.read_resource("markitdown://..%2Fsecret.md")


@pytest.mark.asyncio
async def test_read_markitdown_resource_missing_file(tmp_path: Path) -> None:
    mcp = FastMCP("test")
    register_markitdown_resources(mcp, tmp_path)

    with pytest.raises(ValueError, match="MarkItDown output not found"):
        await mcp.read_resource("markitdown://missing.md")
