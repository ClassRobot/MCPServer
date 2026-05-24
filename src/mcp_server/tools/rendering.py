"""MCP tools for rendering HTML and Markdown content into high-quality images."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from mcp_server.services.rendering import ContentRenderingService


def register_rendering_tools(
    mcp: FastMCP,
    *,
    rendering_service: ContentRenderingService,
) -> None:
    """Register HTML and Markdown image rendering tools."""

    @mcp.tool(
        name="render_content_to_image",
        description=(
            "Render raw HTML or Markdown content into a high-quality PNG image. "
            "Returns the local file path and a base64-encoded image string."
        ),
        structured_output=True,
    )
    async def render_content_to_image(
        content: str,
        input_format: Literal["html", "markdown"],
        theme: Literal["light", "dark"] = "light",
        width: int = 800,
        height: int | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
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

        Returns:
            A dictionary containing:
                - file_path: The absolute local file path where the PNG is saved.
                - base64_image: The base64-encoded string of the PNG bytes.
                - width: The actual viewport width of the rendered image.
                - height: The actual viewport height of the rendered image.
                - input_format: The input format used for rendering.
        """
        result = await rendering_service.render(
            content=content,
            input_format=input_format,
            theme=theme,
            width=width,
            height=height,
            output_path=output_path,
        )
        return asdict(result)
