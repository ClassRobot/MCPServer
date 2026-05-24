"""MCP tools for rendering HTML and Markdown content into high-quality images."""

from __future__ import annotations

from dataclasses import asdict
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
            "Render raw HTML or Markdown content into a high-quality PNG image. "
            "Returns the local file path and a base64-encoded image string."
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
        """Convert HTML or Markdown to an image and return structured results.

        Args:
            content: The raw HTML or Markdown content to render.
            input_format: The format of the content, either 'html' or 'markdown'.
            theme: The color theme for Markdown styling ('light' or 'dark'). Defaults to 'light'.
            width: The target viewport width in pixels. Defaults to 800.
            height: The target viewport height in pixels. If not provided, height is dynamically
                stretched to fit the content exactly without bottom empty space.
            output_path: Optional file path to save the output PNG. If relative, saved in the
                default output directory. If not provided, a random name is generated.
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
            f"Saved to: {result.file_path}"
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
            "Generate a beautiful data chart (line, bar, pie, radar, scatter) as a PNG image "
            "using Apache ECharts. High-fidelity dynamic styling included."
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
        """Convert a structured data payload into an exquisite ECharts visualization snapshot.

        Args:
            chart_type: The visualization form, one of 'line', 'bar', 'pie', 'radar', 'scatter'.
            data: Standard data dict containing:
                - labels: list of strings (x-axis category labels or indicator keys)
                - datasets: list of objects with 'label' (name) and 'data' (values)
                - ECharts custom configuration under the special "option" key overrides all mapping.
            title: The title text rendered at the top center of the chart.
            theme: The visual aesthetic theme, either 'light' or 'dark'. Defaults to 'light'.
            width: Viewport rendering width in pixels. Defaults to 800.
            height: Viewport rendering height in pixels. Defaults to 600.
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
            f"Saved to: {result.file_path}"
        )

        return [
            TextContent(type="text", text=description),
            ImageContent(
                type="image",
                data=result.base64_image,
                mimeType="image/png",
            ),
        ]
