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
            "Render specified pages (or all pages) of a local PDF document into high-fidelity "
            "PNG images. Returns the file paths and base64-encoded image strings."
        ),
        structured_output=True,
    )
    @log_mcp_tool("browser_render_pdf", logging_settings)
    async def browser_render_pdf(
        pdf_path: str,
        pages: list[int] | None = None,
        dpi: int = 150,
    ) -> dict[str, Any]:
        """Render pages of a PDF to images for multi-modal processing.

        Args:
            pdf_path: The local absolute or project-relative file path to the PDF document.
            pages: An optional list of 1-indexed page numbers to render. If not provided,
                renders all pages.
            dpi: The target resolution (dots per inch) for page visual rendering. Defaults to 150.
        """
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

        rendered_pages = []
        for idx in pages_to_render:
            png_bytes, file_path = await pdf_service.render_pdf_page(path, idx, dpi=dpi)
            base64_img = base64.b64encode(png_bytes).decode("utf-8")
            rendered_pages.append(
                {
                    "page": idx + 1,
                    "file_path": file_path,
                    "base64_image": base64_img,
                }
            )

        return {
            "pdf_path": str(path),
            "total_pages": len(pages_to_render),
            "pages": rendered_pages,
        }

    @mcp.tool(
        name="browser_extract_pdf_text",
        description=(
            "Extract structure-preserving plain text from specified pages (or all pages) "
            "of a local PDF document."
        ),
        structured_output=True,
    )
    @log_mcp_tool("browser_extract_pdf_text", logging_settings)
    async def browser_extract_pdf_text(
        pdf_path: str,
        pages: list[int] | None = None,
    ) -> dict[str, Any]:
        """Extract high-fidelity plain text from pages of a PDF document.

        Args:
            pdf_path: The local absolute or project-relative file path to the PDF document.
            pages: An optional list of 1-indexed page numbers to extract text from.
                If not provided, extracts text from all pages.
        """
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

        extracted_pages = []
        for idx in pages_to_extract:
            text = await pdf_service.extract_pdf_text(path, idx)
            extracted_pages.append(
                {
                    "page": idx + 1,
                    "text": text,
                }
            )

        return {
            "pdf_path": str(path),
            "total_pages": len(pages_to_extract),
            "pages": extracted_pages,
        }
