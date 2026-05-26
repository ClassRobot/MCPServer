"""PDF 文档阅读、高保真栅格化渲染及结构化文本提取的业务服务层。

该模块完全基于 Google PDFium (通过 pypdfium2) 和 pypdf 库实现，
完全避免了跨平台部署时对 Poppler 等外部复杂二进制环境的安装依赖。
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from uuid import uuid4

import pypdf
import pypdfium2 as pdfium


class PDFReadingService:
    """PDF 高保真渲染与结构化文本提取服务类。

    提供获取 PDF 页数、将特定页面栅格化渲染为 PNG 图片、以及提取页面中可搜索的纯文本等核心功能。
    """

    def __init__(self, default_output_dir: Path) -> None:
        """初始化 PDF 阅读服务。

        Args:
            default_output_dir (Path): 默认生成的 PNG 渲染图像保存的目标目录。
        """
        self._default_output_dir = default_output_dir
        # 初始化时，递归确保输出目录在磁盘上创建就绪
        self._default_output_dir.mkdir(parents=True, exist_ok=True)

    def get_page_count(self, pdf_path: Path) -> int:
        """获取 PDF 文档的物理总页数。

        Args:
            pdf_path (Path): PDF 实体文件的本地路径。

        Returns:
            int: 该 PDF 的总页数。

        Raises:
            FileNotFoundError: 输入的 PDF 文件在磁盘上未找到。
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # 使用 pypdfium2 高性能只读模式加载并快速返回页数
        with pdfium.PdfDocument(str(pdf_path)) as doc:
            return len(doc)

    async def render_pdf_page(
        self,
        pdf_path: Path,
        page_index: int,
        dpi: int = 150,
        output_path: str | None = None,
    ) -> tuple[bytes, str]:
        """异步栅格化渲染 PDF 文件的特定页面并输出为 PNG 图像。

        为防止 CPU 密集型的渲染计算阻塞 asyncio 的主事件循环，
        本方法将同步的 PDF 渲染细节自动托管至独立的后台线程池中运行。

        Args:
            pdf_path (Path): PDF 文档的本地绝对路径。
            page_index (int): 待渲染页面的基于 0 开始的物理索引。
            dpi (int): 渲染的目标分辨率精度 (DPI)，默认值为 150。
            output_path (str | None): 生成的 PNG 图像的保存路径。若未提供，则在默认输出目录下生成随机文件名。

        Returns:
            tuple[bytes, str]: 由 (PNG图像原始字节流, PNG文件的绝对路径字符串) 构成的二元组。

        Raises:
            FileNotFoundError: 输入的 PDF 文件不存在。
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # 将 CPU 密集型的同步渲染计算任务 offload 派发至 asyncio 默认的工作线程池中执行
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
        """CPU 密集型 PDF 页面物理图像渲染的同步工作线程核心实现。"""
        with pdfium.PdfDocument(str(pdf_path)) as doc:
            num_pages = len(doc)
            # 强边界验证，防页码索引越界
            if page_index < 0 or page_index >= num_pages:
                raise IndexError(
                    f"Page index {page_index} out of bounds for PDF with {num_pages} pages."
                )

            page = doc[page_index]
            # pypdfium2 的缩放系数是以标准的 72 DPI 为底数计算的（例：scale = 2.0 代表以 144 DPI 渲染）
            scale = dpi / 72.0
            pil_image = page.render(scale=scale).to_pil()

            # 将 PIL 内存图像转换为无损压缩的 PNG 字节数据流
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format="PNG")
            png_bytes = img_byte_arr.getvalue()

        # 确定最终写盘的绝对路径
        if output_path:
            resolved_path = Path(output_path)
            if not resolved_path.is_absolute():
                resolved_path = self._default_output_dir / resolved_path
        else:
            # 未指定路径时，自动拼接由 uuid 与 1-based 人类可读页码组成的安全文件名
            resolved_path = (
                self._default_output_dir / f"pdf_page_{uuid4().hex[:8]}_p{page_index + 1}.png"
            )

        # 最终写盘操作：确保所在父目录完整存在并写入二进制图像字节
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_bytes(png_bytes)

        return png_bytes, str(resolved_path)

    async def extract_pdf_text(self, pdf_path: Path, page_index: int) -> str:
        """异步提取指定 PDF 页面的结构化及可搜索文本内容。

        本方法使用 `asyncio.to_thread` 托管底层 CPU 密集型的字符位置解构逻辑。

        Args:
            pdf_path (Path): PDF 文档的本地绝对路径。
            page_index (int): 待提取页面的基于 0 开始的物理索引。

        Returns:
            str: 从页面中安全提取出的纯文本字符内容；若提取失败或无文本，则返回空字符串。

        Raises:
            FileNotFoundError: 输入的 PDF 文件不存在。
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        return await asyncio.to_thread(self._extract_pdf_text_sync, pdf_path, page_index)

    def _extract_pdf_text_sync(self, pdf_path: Path, page_index: int) -> str:
        """执行 PDF 字符流定位与文本提取的同步工作线程核心实现。"""
        reader = pypdf.PdfReader(str(pdf_path))
        num_pages = len(reader.pages)
        # 强边界验证，防页码索引越界
        if page_index < 0 or page_index >= num_pages:
            raise IndexError(
                f"Page index {page_index} out of bounds for PDF with {num_pages} pages."
            )

        page = reader.pages[page_index]
        # 调用 pypdf 内核提取布局合理的物理文本块并做空字符回退
        text = page.extract_text()
        return text or ""
