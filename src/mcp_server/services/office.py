"""Service layer for converting Word and PPT documents to high-fidelity PDF/images."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

from mcp_server.services.pdf_reader import PDFReadingService


class OfficeDocumentService:
    """Service to handle high-fidelity rendering of DOCX and PPTX files.

    Uses LibreOffice headless mode to convert files to PDF, and then leverages
    PDFReadingService to render the pages as PNG images.
    """

    def __init__(self, default_output_dir: Path, pdf_service: PDFReadingService) -> None:
        self._default_output_dir = default_output_dir
        self._pdf_service = pdf_service
        self._soffice_path = self._locate_soffice()

    def _locate_soffice(self) -> Path | None:
        """Find the LibreOffice (soffice) executable on the current system."""
        # 1. Search system PATH
        executable = shutil.which("soffice") or shutil.which("libreoffice")
        if executable:
            return Path(executable)

        # 2. Search Windows-specific installations
        if sys.platform == "win32":
            user_profile = os.getenv("USERPROFILE", "")
            if user_profile:
                scoop_paths = [
                    Path(user_profile) / "scoop/shims/soffice.exe",
                    Path(user_profile) / "scoop/shims/libreoffice.exe",
                    Path(user_profile) / "scoop/apps/libreoffice/current/program/soffice.exe",
                ]
                for p in scoop_paths:
                    if p.is_file():
                        return p

            program_files = [
                Path("C:\\Program Files\\LibreOffice\\program\\soffice.exe"),
                Path("C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe"),
            ]
            for p in program_files:
                if p.is_file():
                    return p

        return None

    async def convert_to_pdf(self, doc_path: Path, output_dir: Path) -> Path:
        """Convert a Word or PPT document to PDF using LibreOffice in headless mode.

        Args:
            doc_path: Absolute Path to the source DOCX/PPTX file.
            output_dir: Path where the generated PDF should be saved.

        Returns:
            The Path of the generated PDF file.
        """
        if not self._soffice_path:
            raise RuntimeError(
                "LibreOffice (soffice) executable was not found on this system.\n"
                "Please install LibreOffice and ensure it is in your system PATH.\n"
                "On Windows via Scoop: run `scoop install libreoffice`.\n"
                "On Linux: run `sudo apt-get install libreoffice`."
            )

        if not doc_path.is_file():
            raise FileNotFoundError(f"Document file not found: {doc_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Command: soffice --headless --convert-to pdf --outdir <output_dir> <doc_path>
        cmd = [
            str(self._soffice_path),
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(doc_path),
        ]

        # Use non-blocking async subprocess execution
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await process.wait()

        if process.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed with exit code {process.returncode}")

        generated_pdf = output_dir / f"{doc_path.stem}.pdf"
        if not generated_pdf.is_file():
            raise FileNotFoundError(f"Expected converted PDF not found at {generated_pdf}")

        return generated_pdf

    async def render_document(
        self,
        doc_path: Path,
        pages: list[int] | None = None,
        dpi: int = 150,
    ) -> list[tuple[bytes, Path]]:
        """Convert document to temporary PDF and render target pages as PNG images.

        Args:
            doc_path: Path to the source DOCX/PPTX document.
            pages: Optional list of 1-indexed page/slide numbers to render.
            dpi: The target rendering resolution (DPI).

        Returns:
            A list of tuples containing (png_bytes, file_path).
        """
        pdf_path = await self.convert_to_pdf(doc_path, self._default_output_dir)

        try:
            total_pages = self._pdf_service.get_page_count(pdf_path)

            pages_to_render = []
            if pages is None:
                pages_to_render = list(range(total_pages))
            else:
                for p in pages:
                    if p < 1 or p > total_pages:
                        raise IndexError(
                            f"Page/slide number {p} is out of bounds (1-{total_pages})."
                        )
                    pages_to_render.append(p - 1)

            results: list[tuple[bytes, Path]] = []
            for idx in pages_to_render:
                png_bytes, file_path_str = await self._pdf_service.render_pdf_page(
                    pdf_path,
                    idx,
                    dpi=dpi,
                )
                results.append((png_bytes, Path(file_path_str)))

            return results

        finally:
            # Clean up the temporary PDF file immediately
            if pdf_path.is_file():
                try:
                    pdf_path.unlink()
                except Exception:
                    pass
