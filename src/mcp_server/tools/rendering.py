"""MCP tools for rendering HTML and Markdown content into high-quality images."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.rendering import ContentRenderingService
from mcp_server.tool_logging import log_mcp_tool


def register_rendering_tools(
    mcp: FastMCP,
    *,
    rendering_service: ContentRenderingService,
    logging_settings: LoggingSettings,
) -> None:
    """Register HTML and Markdown image rendering tools."""

    @mcp.tool(
        name="render_content_to_image",
        description=(
            "Convert raw HTML or Markdown content into a high-fidelity PNG image. "
            "Useful for visualizing complex layouts, formatted text, or previewing web content "
            "directly within the AI conversation."
        ),
    )
    @log_mcp_tool("render_content_to_image", logging_settings)
    async def render_content_to_image(
        content: str,
        input_format: Literal["html", "markdown"],
        theme: Literal["light", "dark"] = "light",
        width: int = 800,
        height: int | None = None,
        output_path: str | None = None,
    ) -> list[Any]:
        """Convert HTML or Markdown to an image.

        Args:
            content: The raw HTML or Markdown string to be rendered.
            input_format: The format of the input content ('html' or 'markdown').
            theme: The visual theme for Markdown rendering ('light' or 'dark').
            width: The target viewport width in pixels (default: 800).
            height: The target viewport height in pixels. If None, auto-stretches to fit content.
            output_path: Optional path to save the PNG file. Relative paths are saved in the
                default render directory.
        """
        from mcp.types import ImageContent, TextContent

        result = await rendering_service.render(
            content=content,
            input_format=input_format,
            theme=theme,
            width=width,
            height=height,
            output_path=output_path,
        )

        description = (
            f"Successfully rendered {input_format} content to image.\n"
            f"Dimensions: {result.width}x{result.height}px\n"
            f"Local Path: {result.file_path}\n"
            f"Resource URI: render://{Path(result.file_path).name}"
        )

        return [
            TextContent(type="text", text=description),
            ImageContent(
                type="image",
                data=result.base64_image,
                mimeType="image/png",
            ),
        ]

    @mcp.tool(
        name="render_data_chart",
        description=(
            "Generate professional data visualizations (line, bar, pie, radar, scatter) as "
            "high-quality PNG images using Apache ECharts. "
            "Perfect for presenting data insights visually to the user."
        ),
    )
    @log_mcp_tool("render_data_chart", logging_settings)
    async def render_data_chart(
        chart_type: Literal["line", "bar", "pie", "radar", "scatter"],
        data: dict[str, Any],
        title: str | None = None,
        theme: Literal["light", "dark"] = "light",
        width: int = 800,
        height: int = 600,
        output_path: str | None = None,
    ) -> list[Any]:
        """Generate a data chart image.

        Args:
            chart_type: The type of chart to generate.
            data: Structured data for the chart. Must include 'labels' (list of strings) and
                'datasets' (list of objects with 'label' and 'data' keys).
                Alternatively, provide a full ECharts 'option' object for complete control.
            title: The main title displayed on the chart.
            theme: The visual aesthetic theme ('light' or 'dark').
            width: The image width in pixels (default: 800).
            height: The image height in pixels (default: 600).
            output_path: Optional exact path to save the output PNG file.
        """
        from mcp.types import ImageContent, TextContent

        result = await rendering_service.render_chart(
            chart_type=chart_type,
            data=data,
            title=title,
            theme=theme,
            width=width,
            height=height,
            output_path=output_path,
        )

        description = (
            f"Successfully generated {chart_type} chart: {title or 'Untitled'}\n"
            f"Dimensions: {result.width}x{result.height}px\n"
            f"Local Path: {result.file_path}\n"
            f"Resource URI: render://{Path(result.file_path).name}"
        )

        return [
            TextContent(type="text", text=description),
            ImageContent(
                type="image",
                data=result.base64_image,
                mimeType="image/png",
            ),
        ]
