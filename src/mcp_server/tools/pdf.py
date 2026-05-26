"""调用纯 Python 无 poppler 依赖 PDF 核心服务执行高保真视觉渲染及文本提取的 MCP 工具接口层。"""

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
    """在 FastMCP 实例上注册 PDF 文件提取及高保真排版图像渲染工具。

    Args:
        mcp (FastMCP): FastMCP 服务应用程序实例。
        pdf_service (PDFReadingService): PDF 文档高保真提取及渲染服务。
        project_root (Path): 本项目根目录的物理路径，用于折算相对路径。
        logging_settings (LoggingSettings): 全局日志记录审计配置。
    """

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
        """将本地 PDF 文件的指定页面高保真渲染输出为 PNG 图像。

        Args:
            pdf_path (str): 本地 PDF 文件的路径，支持相对路径（自动折算）。
            pages (list[int] | None): 基于 1 开始的待渲染页码列表，若为 None 则默认渲染全部页面。
            dpi (int): 渲染的分辨率精度 (DPI)，默认值为 150。

        Returns:
            list[Any]: 包含说明、动态资源 URI 路径及 Base64 编码图像数据的 MCP 混合资产列表。
        """
        from mcp.types import ImageContent, TextContent

        # 折算路径
        path = Path(pdf_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"PDF file does not exist at path: {path}")

        # 获取文档物理总页码
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

        # 逐页进行渲染转换并拼装 MCP 消息体
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
        """提取指定 PDF 页面中布局规整的可搜索纯文本内容。

        Args:
            pdf_path (str): 本地 PDF 文件的路径，支持相对路径。
            pages (list[int] | None): 基于 1 开始的页码列表；若为 None 则提取全部。

        Returns:
            list[Any]: 包含结构化页面文本的 MCP 文本清单。
        """
        from mcp.types import TextContent

        # 折算路径
        path = Path(pdf_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"PDF file does not exist at path: {path}")

        # 获取文档物理总页码
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

        # 逐页进行纯文本提取
        for idx in pages_to_extract:
            text = await pdf_service.extract_pdf_text(path, idx)
            contents.append(
                TextContent(
                    type="text",
                    text=f"--- Page {idx + 1} ---\n{text}",
                )
            )

        return contents
