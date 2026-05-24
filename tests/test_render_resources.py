"""Tests for the dynamic MCP render resources module."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server.resources.render import register_render_resources


@pytest.mark.asyncio
async def test_read_render_resource_success(tmp_path: Path) -> None:
    """Verify that a generated file can be successfully retrieved via the resource URI."""
    mcp = FastMCP("test")
    register_render_resources(mcp, tmp_path)

    test_file = tmp_path / "screenshot_123.png"
    test_file.write_bytes(b"FAKE_PNG_BYTES")

    contents = await mcp.read_resource("render://screenshot_123.png")

    assert len(contents) == 1
    assert contents[0].content == b"FAKE_PNG_BYTES"


@pytest.mark.asyncio
async def test_read_render_resource_directory_traversal_prevention(tmp_path: Path) -> None:
    """Verify that directory traversal attempts are securely blocked with a ValueError."""
    mcp = FastMCP("test")
    register_render_resources(mcp, tmp_path)

    with pytest.raises(ValueError, match="Directory traversal attempt detected."):
        await mcp.read_resource("render://..%2Ftest_logging.py")

    with pytest.raises(ValueError, match="Directory traversal attempt detected."):
        await mcp.read_resource("render://..\\test_logging.py")

    with pytest.raises(ValueError, match="Unknown resource:"):
        await mcp.read_resource("render:///absolute/path/to/some/file.png")


@pytest.mark.asyncio
async def test_read_render_resource_file_not_found(tmp_path: Path) -> None:
    """Verify that requesting a missing file raises ValueError with expected message."""
    mcp = FastMCP("test")
    register_render_resources(mcp, tmp_path)

    with pytest.raises(ValueError, match="Rendered file not found: missing_file.png"):
        await mcp.read_resource("render://missing_file.png")
