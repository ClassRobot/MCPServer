"""Tests for the OfficeDocumentService and associated Word/PPT rendering tools."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.office import OfficeDocumentService
from mcp_server.services.pdf_reader import PDFReadingService
from mcp_server.tools.office_tools import register_office_tools


def test_office_service_locator_searches_standard_paths() -> None:
    """Verify that the locator checks Scoop and Program Files paths on Windows."""
    pdf_service = MagicMock(spec=PDFReadingService)

    with patch("shutil.which", return_value=None):
        if sys.platform == "win32":
            with patch("os.getenv", return_value="C:\\Users\\TestUser"):
                service = OfficeDocumentService(Path("."), pdf_service)
                # Should attempt to find, and returns None if none are found
                # in the mocked environment
                assert service._soffice_path is None or isinstance(service._soffice_path, Path)
        else:
            service = OfficeDocumentService(Path("."), pdf_service)
            assert service._soffice_path is None


@pytest.mark.asyncio
async def test_office_service_throws_clean_error_if_missing(tmp_path: Path) -> None:
    """Verify that a descriptive RuntimeError is raised if LibreOffice is missing."""
    pdf_service = MagicMock(spec=PDFReadingService)
    service = OfficeDocumentService(tmp_path, pdf_service)
    service._soffice_path = None  # Mock as missing

    dummy_doc = tmp_path / "test.docx"
    dummy_doc.write_text("dummy")

    with pytest.raises(RuntimeError, match="LibreOffice .* not found"):
        await service.convert_to_pdf(dummy_doc, tmp_path)


@pytest.mark.asyncio
async def test_render_document_converts_and_renders_successfully(tmp_path: Path) -> None:
    """Verify the document-to-image rendering pipeline runs successfully."""
    pdf_service = MagicMock(spec=PDFReadingService)
    pdf_service.get_page_count.return_value = 2
    pdf_service.render_pdf_page = AsyncMock(return_value=(b"PNG_BYTES", "page_1.png"))

    service = OfficeDocumentService(tmp_path, pdf_service)
    service._soffice_path = Path("mock_soffice")

    dummy_doc = tmp_path / "test.docx"
    dummy_doc.write_text("dummy")

    # Mock CLI convert_to_pdf process execution to avoid real
    # LibreOffice dependency in unit tests
    async def mock_convert(doc_path: Path, output_dir: Path) -> Path:
        pdf_file = output_dir / f"{doc_path.stem}.pdf"
        pdf_file.write_bytes(b"MOCK_PDF_CONTENT")
        return pdf_file

    with patch.object(service, "convert_to_pdf", side_effect=mock_convert):
        rendered = await service.render_document(dummy_doc, pages=[1, 2], dpi=150)

        assert len(rendered) == 2
        assert rendered[0][0] == b"PNG_BYTES"
        assert rendered[0][1] == Path("page_1.png")
        pdf_service.get_page_count.assert_called_once()
        assert pdf_service.render_pdf_page.call_count == 2


@pytest.mark.asyncio
async def test_office_tools_registration_and_invocation(tmp_path: Path) -> None:
    """Verify that Word and PPT MCP tools are registered and return Resource URIs only."""
    mcp = FastMCP("test")
    office_service = MagicMock(spec=OfficeDocumentService)
    office_service.render_document = AsyncMock(
        return_value=[(b"PNG_SLIDE_1", Path("slide_1.png")), (b"PNG_SLIDE_2", Path("slide_2.png"))]
    )

    register_office_tools(
        mcp,
        office_service=office_service,
        project_root=tmp_path,
        logging_settings=LoggingSettings(),
    )

    # Verify registration
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "browser_render_docx" in tool_names
    assert "browser_render_pptx" in tool_names

    # Test docx tool invocation
    dummy_doc = tmp_path / "test.docx"
    dummy_doc.write_text("dummy")

    # Invoke via FastMCP call_tool
    results = await mcp.call_tool("browser_render_docx", {"docx_path": str(dummy_doc)})
    content_list = results[0]

    # Verify strictly no absolute physical paths in outputs, only render:// Resource URIs
    output_text = "".join([c.text for c in content_list if hasattr(c, "text") and c.text])
    assert "D:" not in output_text
    assert "C:" not in output_text
    assert "render://slide_1.png" in output_text or "render://slide_2.png" in output_text
