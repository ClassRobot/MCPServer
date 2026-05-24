"""Asynchronous unit tests for PDFReadingService utilizing standard mock strategies."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_server.services.pdf_reader import PDFReadingService


@pytest.mark.asyncio
async def test_pdf_get_page_count() -> None:
    """Test getting page count from a mock PDF."""
    service = PDFReadingService(default_output_dir=Path("runtime/test_render"))

    with patch("pypdfium2.PdfDocument") as mock_doc_class, patch(
        "pathlib.Path.exists"
    ) as mock_exists:
        mock_exists.return_value = True
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__len__.return_value = 5
        mock_doc_class.return_value = mock_doc

        count = service.get_page_count(Path("dummy.pdf"))
        assert count == 5
        mock_doc_class.assert_called_once_with("dummy.pdf")


@pytest.mark.asyncio
async def test_pdf_extract_text() -> None:
    """Test extracting structure-preserving plain text from mock PDF pages."""
    service = PDFReadingService(default_output_dir=Path("runtime/test_render"))

    with patch("pypdf.PdfReader") as mock_reader_class, patch(
        "pathlib.Path.exists"
    ) as mock_exists:
        mock_exists.return_value = True
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello world from PDF!"
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        # Test valid page extraction
        text = await service.extract_pdf_text(Path("dummy.pdf"), 0)
        assert text == "Hello world from PDF!"
        mock_page.extract_text.assert_called_once()

        # Test index out of bounds error
        with pytest.raises(IndexError):
            await service.extract_pdf_text(Path("dummy.pdf"), 5)


@pytest.mark.asyncio
async def test_pdf_render_page() -> None:
    """Test rendering page visual snapshot mock."""
    service = PDFReadingService(default_output_dir=Path("runtime/test_render"))

    with patch("pypdfium2.PdfDocument") as mock_doc_class, patch(
        "pathlib.Path.exists"
    ) as mock_exists, patch("pathlib.Path.write_bytes") as mock_write:
        mock_exists.return_value = True
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_page = MagicMock()
        mock_doc.__len__.return_value = 3
        mock_doc.__getitem__.return_value = mock_page

        mock_pil = MagicMock()
        mock_page.render.return_value.to_pil.return_value = mock_pil

        mock_doc_class.return_value = mock_doc

        # Execute render page
        png_bytes, file_path = await service.render_pdf_page(Path("dummy.pdf"), 0)
        assert isinstance(png_bytes, bytes)
        assert "pdf_page_" in file_path
        mock_page.render.assert_called_once()
        mock_pil.save.assert_called_once()
        mock_write.assert_called_once()
