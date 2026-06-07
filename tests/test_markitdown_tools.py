"""Tests for MarkItDown MCP tool registration and invocation."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings, MarkItDownSettings
from mcp_server.services.markitdown import MarkItDownConversionService
from mcp_server.tools.markitdown import register_markitdown_tools


class FakeMarkItDownService(MarkItDownConversionService):
    """Avoid importing the third-party converter in tool registration tests."""

    def convert_local_file(self, source_path: Path) -> str:
        return "# Converted\n"


@pytest.mark.asyncio
async def test_markitdown_tool_registration_and_invocation(tmp_path: Path) -> None:
    mcp = FastMCP("test")
    source_file = tmp_path / "sample.txt"
    source_file.write_text("hello", encoding="utf-8")
    service = FakeMarkItDownService(
        MarkItDownSettings(
            allowed_roots=(tmp_path,),
            output_dir=tmp_path / "out",
            save_output_by_default=False,
        ),
        project_root=tmp_path,
    )

    register_markitdown_tools(
        mcp,
        markitdown_service=service,
        logging_settings=LoggingSettings(),
    )

    tools = await mcp.list_tools()
    assert "convert_to_markdown" in {tool.name for tool in tools}

    _, payload = await mcp.call_tool("convert_to_markdown", {"uri": "sample.txt"})

    assert payload["source_name"] == "sample.txt"
    assert payload["markdown"] == "# Converted\n"
    assert payload["output_resource_uri"] is None
