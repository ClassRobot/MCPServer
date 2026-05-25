"""MCP tools for rendering DOCX and PPTX documents to high-fidelity preview images."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.office import OfficeDocumentService
from mcp_server.tool_logging import log_mcp_tool


def register_office_tools(
    mcp: FastMCP,
    *,
    office_service: OfficeDocumentService,
    project_root: Path,
    logging_settings: LoggingSettings,
) -> None:
    """Register Word and PPT visual rendering tools on FastMCP."""

    @mcp.tool(
        name="browser_render_docx",
        description=(
            "Render specified pages (or all pages) of a local Word document (.docx) "
            "into high-fidelity PNG preview images. "
            "Returns network-compliant Resource URIs and inline visual previews."
        ),
    )
    @log_mcp_tool("browser_render_docx", logging_settings)
    async def browser_render_docx(
        docx_path: str,
        pages: list[int] | None = None,
        dpi: int = 150,
    ) -> list[Any]:
        """Render Word document pages to preview images.

        Args:
            docx_path: Path to the Word document. Relative paths resolved against project root.
            pages: Optional list of 1-indexed page numbers to render. If omitted, renders all.
            dpi: Target visual resolution (DPI). Defaults to 150.
        """
        from mcp.types import ImageContent, TextContent

        path = Path(docx_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.is_file():
            raise FileNotFoundError(f"Word document file does not exist: {docx_path}")

        rendered_pages = await office_service.render_document(
            path,
            pages=pages,
            dpi=dpi,
        )

        contents: list[Any] = []
        description = (
            f"Successfully rendered Word document: {path.name}\n"
            f"Total rendered pages: {len(rendered_pages)}"
        )
        contents.append(TextContent(type="text", text=description))

        for idx, (png_bytes, file_path) in enumerate(rendered_pages):
            filename = file_path.name
            contents.append(
                TextContent(
                    type="text",
                    text=(
                        f"Page {pages[idx] if pages else idx + 1} rendering:\n"
                        f"  - Resource URI: render://{filename}"
                    ),
                )
            )
            contents.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(png_bytes).decode("utf-8"),
                    mimeType="image/png",
                )
            )

        return contents

    @mcp.tool(
        name="browser_render_pptx",
        description=(
            "Render specified slides (or all slides) of a local PowerPoint presentation (.pptx) "
            "into high-fidelity PNG preview images. "
            "Returns network-compliant Resource URIs and inline visual previews."
        ),
    )
    @log_mcp_tool("browser_render_pptx", logging_settings)
    async def browser_render_pptx(
        pptx_path: str,
        slides: list[int] | None = None,
        dpi: int = 150,
    ) -> list[Any]:
        """Render PowerPoint slides to preview images.

        Args:
            pptx_path: Path to the target PPTX file. Relative paths resolved against project root.
            slides: Optional list of 1-indexed slide numbers to render (default: all slides).
            dpi: Target visual resolution (DPI). Defaults to 150.
        """
        from mcp.types import ImageContent, TextContent

        path = Path(pptx_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.is_file():
            raise FileNotFoundError(f"PowerPoint file does not exist: {pptx_path}")

        rendered_slides = await office_service.render_document(
            path,
            pages=slides,
            dpi=dpi,
        )

        contents: list[Any] = []
        description = (
            f"Successfully rendered PowerPoint presentation: {path.name}\n"
            f"Total rendered slides: {len(rendered_slides)}"
        )
        contents.append(TextContent(type="text", text=description))

        for idx, (png_bytes, file_path) in enumerate(rendered_slides):
            filename = file_path.name
            contents.append(
                TextContent(
                    type="text",
                    text=(
                        f"Slide {slides[idx] if slides else idx + 1} rendering:\n"
                        f"  - Resource URI: render://{filename}"
                    ),
                )
            )
            contents.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(png_bytes).decode("utf-8"),
                    mimeType="image/png",
                )
            )

        return contents
