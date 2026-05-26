"""调用无头 Office 转换服务将 Word 和 PPT 文档高保真渲染为高清 PNG 预览图像的 MCP 工具接口层。"""

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
    """在 FastMCP 实例上注册 Word 及 PowerPoint 高保真排版图像渲染工具。

    Args:
        mcp (FastMCP): FastMCP 服务应用程序实例。
        office_service (OfficeDocumentService): Word/PPT 办公文档转换及渲染服务。
        project_root (Path): 本项目根目录的物理路径，用于折算相对路径。
        logging_settings (LoggingSettings): 全局日志记录审计配置。
    """

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
        """将本地 DOCX 格式的 Word 文档特定页面高保真渲染输出为 PNG 预览图。

        Args:
            docx_path (str): Word 文档在磁盘上的路径，相对路径会基于项目根目录自动折算。
            pages (list[int] | None): 待渲染的基于 1 开始索引的页码列表；若为 None 则默认渲染全部页面。
            dpi (int): 渲染的目标分辨率精度 (DPI)，默认值为 150。

        Returns:
            list[Any]: 包含说明文本、动态资源 URI 路径及 Base64 编码图像数据的 MCP 混合资产列表。
        """
        from mcp.types import ImageContent, TextContent

        # 折算相对路径为绝对路径
        path = Path(docx_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.is_file():
            raise FileNotFoundError(f"Word document file does not exist: {docx_path}")

        # 调用核心办公文档转换服务转换并渲染为高清图像
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

        # 逐页封包图像资产及资源 URI
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
        """将本地 PPTX 格式的 PowerPoint 幻灯片特定页面高保真渲染输出为 PNG 预览图。

        Args:
            pptx_path (str): PPTX 文件的物理路径，相对路径自动折算。
            slides (list[int] | None): 待渲染的基于 1 开始索引的幻灯片页码列表；若为 None 则默认渲染全部。
            dpi (int): 渲染的目标分辨率精度 (DPI)，默认值为 150。

        Returns:
            list[Any]: 包含说明文本、动态资源 URI 路径及 Base64 编码图像数据的 MCP 混合资产列表。
        """
        from mcp.types import ImageContent, TextContent

        # 折算相对路径为绝对路径
        path = Path(pptx_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()

        if not path.is_file():
            raise FileNotFoundError(f"PowerPoint file does not exist: {pptx_path}")

        # 调用办公文档服务完成渲染转换
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

        # 逐页封包图像资产及资源 URI
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
