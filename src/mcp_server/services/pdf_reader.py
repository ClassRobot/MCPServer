"""Service layer for reading, rendering, and extracting text from PDF files."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from uuid import uuid4

import pypdf
import pypdfium2 as pdfium


class PDFReadingService:
    """High-fidelity PDF visual rendering and text extraction service.

    Relying purely on Google PDFium via pypdfium2 and pypdf, completely eliminating
    any cross-platform poppler binary installation requirements.
    """

    def __init__(self, default_output_dir: Path) -> None:
        self._default_output_dir = default_output_dir
        self._default_output_dir.mkdir(parents=True, exist_ok=True)

    def get_page_count(self, pdf_path: Path) -> int:
        """Get the total page count of a PDF file."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Use pypdfium2 to quickly open and count pages
        with pdfium.PdfDocument(str(pdf_path)) as doc:
            return len(doc)

    async def render_pdf_page(
        self,
        pdf_path: Path,
        page_index: int,
        dpi: int = 150,
        output_path: str | None = None,
    ) -> tuple[bytes, str]:
        """Render a specific 0-indexed page of a PDF file to a PNG image.

        Runs the rendering logic in a separate thread to ensure non-blocking execution.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Execute blocking PDFium rendering in threadpool
        return await asyncio.to_thread(
            self._render_pdf_page_sync,
            pdf_path,
            page_index,
            dpi,
            output_path,
        )

    def _render_pdf_page_sync(
        self,
        pdf_path: Path,
        page_index: int,
        dpi: int,
        output_path: str | None = None,
    ) -> tuple[bytes, str]:
        """Synchronous CPU-bound PDF page visual rendering helper."""
        with pdfium.PdfDocument(str(pdf_path)) as doc:
            num_pages = len(doc)
            if page_index < 0 or page_index >= num_pages:
                raise IndexError(
                    f"Page index {page_index} out of bounds for PDF with {num_pages} pages."
                )

            page = doc[page_index]
            # pypdfium2 scale is factor of 72 DPI (e.g. scale=2.0 renders at 144 DPI)
            scale = dpi / 72.0
            pil_image = page.render(scale=scale).to_pil()

            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format="PNG")
            png_bytes = img_byte_arr.getvalue()

        # Resolve output path
        if output_path:
            resolved_path = Path(output_path)
            if not resolved_path.is_absolute():
                resolved_path = self._default_output_dir / resolved_path
        else:
            resolved_path = (
                self._default_output_dir / f"pdf_page_{uuid4().hex[:8]}_p{page_index + 1}.png"
            )

        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_bytes(png_bytes)

        return png_bytes, str(resolved_path)

    async def extract_pdf_text(self, pdf_path: Path, page_index: int) -> str:
        """Extract structure-preserving text from a specific 0-indexed page of a PDF."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        return await asyncio.to_thread(self._extract_pdf_text_sync, pdf_path, page_index)

    def _extract_pdf_text_sync(self, pdf_path: Path, page_index: int) -> str:
        """Synchronous PDF text extraction helper."""
        reader = pypdf.PdfReader(str(pdf_path))
        num_pages = len(reader.pages)
        if page_index < 0 or page_index >= num_pages:
            raise IndexError(
                f"Page index {page_index} out of bounds for PDF with {num_pages} pages."
            )

        page = reader.pages[page_index]
        text = page.extract_text()
        return text or ""
