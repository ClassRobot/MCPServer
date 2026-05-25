"""MCP tools for high-fidelity PDF reading, visual rendering, and text extraction."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.pdf_reader import PDFReadingService
from mcp_server.tool_logging import log_mcp_tool


def register_pdf_tools(
    mcp: FastMCP,
    *,
    pdf_service: PDFReadingService,
    project_root: Path,
    logging_settings: LoggingSettings,
) -> None:
    """Register pure-Python poppler-free PDF reading and visual rendering tools."""

    @mcp.tool(
        name="browser_render_pdf",
        description=(
            "Render specific pages of a local PDF document into high-fidelity PNG images. "
            "Essential for multi-modal AI to 'see' and analyze the visual layout, charts, "
            "and images within a PDF."
        ),
    )
    @log_mcp_tool("browser_render_pdf", logging_settings)
    async def browser_render_pdf(
        pdf_path: str,
        pages: list[int] | None = None,
        dpi: int = 150,
    ) -> list[Any]:
        """Render PDF pages to images.

        Args:
            pdf_path: The local filesystem path to the PDF file (absolute or project-relative).
            pages: List of 1-indexed page numbers to render (e.g., [1, 3, 5]).
                If None, all pages are rendered.
            dpi: Resolution for rendering (default: 150). Higher DPI means better quality but
                larger images.
        """
        from mcp.types import ImageContent, TextContent

        path = Path(pdf_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"PDF file does not exist at path: {path}")

        total_pages = pdf_service.get_page_count(path)

        if pages is None:
            pages_to_render = list(range(total_pages))
        else:
            pages_to_render = []
            for p in pages:
                if p < 1 or p > total_pages:
                    raise IndexError(
                        f"Page number {p} is out of bounds for PDF with {total_pages} pages."
                    )
                pages_to_render.append(p - 1)

        contents: list[Any] = []
        description = (
            f"Successfully rendered {len(pages_to_render)} pages from {path.name}.\n"
            f"Total pages in document: {total_pages}"
        )
        contents.append(TextContent(type="text", text=description))

        for idx in pages_to_render:
            png_bytes, file_path = await pdf_service.render_pdf_page(path, idx, dpi=dpi)
            base64_img = base64.b64encode(png_bytes).decode("utf-8")
            file_name = Path(file_path).name
            contents.append(
                TextContent(
                    type="text",
                    text=(f"Page {idx + 1} rendering:\n  - Resource URI: render://{file_name}"),
                )
            )
            contents.append(
                ImageContent(
                    type="image",
                    data=base64_img,
                    mimeType="image/png",
                )
            )

        return contents

    @mcp.tool(
        name="browser_extract_pdf_text",
        description=(
            "Extract structure-preserving plain text from specific pages of a local PDF document. "
            "Use this for fast text analysis, searching, or summarization of PDF content."
        ),
    )
    @log_mcp_tool("browser_extract_pdf_text", logging_settings)
    async def browser_extract_pdf_text(
        pdf_path: str,
        pages: list[int] | None = None,
    ) -> list[Any]:
        """Extract text from PDF pages.

        Args:
            pdf_path: The local filesystem path to the PDF file (absolute or project-relative).
            pages: List of 1-indexed page numbers to extract text from (e.g., [1, 2]).
                If None, extracts from all pages.
        """
        from mcp.types import TextContent

        path = Path(pdf_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"PDF file does not exist at path: {path}")

        total_pages = pdf_service.get_page_count(path)

        if pages is None:
            pages_to_extract = list(range(total_pages))
        else:
            pages_to_extract = []
            for p in pages:
                if p < 1 or p > total_pages:
                    raise IndexError(
                        f"Page number {p} is out of bounds for PDF with {total_pages} pages."
                    )
                pages_to_extract.append(p - 1)

        contents = []
        contents.append(
            TextContent(
                type="text",
                text=(
                    f"Extracted {len(pages_to_extract)} pages from {path.name} "
                    f"(Total: {total_pages})"
                ),
            )
        )

        for idx in pages_to_extract:
            text = await pdf_service.extract_pdf_text(path, idx)
            contents.append(
                TextContent(
                    type="text",
                    text=f"--- Page {idx + 1} ---\n{text}",
                )
            )

        return contents
