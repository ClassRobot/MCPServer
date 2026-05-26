"""Word 和 PPT 办公文档高保真 PDF/图像转换的业务服务层。

该模块封装了调用 headless 模式的 LibreOffice (soffice) 将 Office 格式文档转换为 PDF 的逻辑，
并能够协同 PDF 阅读服务将 PDF 页面高保真渲染为 PNG 图像。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

from mcp_server.services.pdf_reader import PDFReadingService


class OfficeDocumentService:
    """Office 文档高保真渲染服务类。

    提供将 DOCX、PPTX 等 Office 办公文档转换为 PDF，
    以及将其各页面高保真渲染输出为 PNG 字节流与实体文件的核心业务能力。
    """

    def __init__(self, default_output_dir: Path, pdf_service: PDFReadingService) -> None:
        """初始化 Office 文档转换服务。

        Args:
            default_output_dir (Path): 默认生成的临时 PDF 及图像的输出目录路径。
            pdf_service (PDFReadingService): 协同工作的 PDF 高保真渲染与阅读服务实例。
        """
        self._default_output_dir = default_output_dir
        self._pdf_service = pdf_service
        self._soffice_path = self._locate_soffice()

    def _locate_soffice(self) -> Path | None:
        """在当前系统环境中智能检索 LibreOffice (soffice) 的可执行文件路径。

        检索策略优先查找系统 PATH 环境变量，若未命中则在 Windows 环境下进一步检索
        常见的 Scoop 安装垫片(shims)路径及常规 Program Files 安装路径。

        Returns:
            Path | None: 命中的 soffice.exe 绝对路径；若未安装或未找到则返回 None。
        """
        # 1. 优先搜索系统 PATH 环境变量中的可执行程序
        executable = shutil.which("soffice") or shutil.which("libreoffice")
        if executable:
            return Path(executable)

        # 2. 针对 Windows 系统，深度适配特定软件管理工具及默认安装目录
        if sys.platform == "win32":
            user_profile = os.getenv("USERPROFILE", "")
            if user_profile:
                # 检索 Windows 平台下主流包管理器 Scoop 的默认安装及垫片路径
                scoop_paths = [
                    Path(user_profile) / "scoop/shims/soffice.exe",
                    Path(user_profile) / "scoop/shims/libreoffice.exe",
                    Path(user_profile) / "scoop/apps/libreoffice/current/program/soffice.exe",
                ]
                for p in scoop_paths:
                    if p.is_file():
                        return p

            # 检索 LibreOffice 在 Windows 平台的默认 64 位及 32 位官方安装路径
            program_files = [
                Path("C:\\Program Files\\LibreOffice\\program\\soffice.exe"),
                Path("C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe"),
            ]
            for p in program_files:
                if p.is_file():
                    return p

        return None

    async def convert_to_pdf(self, doc_path: Path, output_dir: Path) -> Path:
        """调用无头(headless)模式的 LibreOffice 将指定的 Word 或 PPT 文档安全转换为 PDF。

        Args:
            doc_path (Path): 待转换的源 DOCX/PPTX 文件的绝对路径。
            output_dir (Path): 转换后生成的 PDF 文件的存放目录。

        Returns:
            Path: 生成的 PDF 文件的绝对路径。

        Raises:
            RuntimeError: 系统未检测到 LibreOffice 环境，或底层进程转换返回了非零退出码。
            FileNotFoundError: 待转换文件不存在，或转换完成后在目标目录未找到生成的 PDF。
        """
        # 拦截校验：检查 LibreOffice 环境依赖是否就绪
        if not self._soffice_path:
            raise RuntimeError(
                "LibreOffice (soffice) executable was not found on this system.\n"
                "Please install LibreOffice and ensure it is in your system PATH.\n"
                "On Windows via Scoop: run `scoop install libreoffice`.\n"
                "On Linux: run `sudo apt-get install libreoffice`."
            )

        if not doc_path.is_file():
            raise FileNotFoundError(f"Document file not found: {doc_path}")

        # 确保输出目标文件夹在写盘前已递归创建
        output_dir.mkdir(parents=True, exist_ok=True)

        # 构建命令行：soffice --headless --convert-to pdf --outdir <output_dir> <doc_path>
        cmd = [
            str(self._soffice_path),
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(doc_path),
        ]

        # 采用非阻塞异步子进程执行命令行转换，防止因大文件渲染导致主事件循环挂起
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await process.wait()

        # 检查转换进程状态码是否正常
        if process.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed with exit code {process.returncode}")

        # 验证输出的 PDF 实体文件是否存在
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
        """将 Office 文档转换为临时 PDF，随后将指定的页面栅格化渲染为 PNG 高清图像。

        本方法封装了端到端转换：先转为中间 PDF 介质，提取特定页面渲染，并在最后无论成功与否都自动清理临时 PDF。

        Args:
            doc_path (Path): Word/PPT 等源办公文档的本地路径。
            pages (list[int] | None): 待渲染的基于 1 开始索引的页码/幻灯片列表。若为 None 则默认渲染全部页面。
            dpi (int): 目标图像的渲染分辨率精度 (DPI)，默认值为 150。

        Returns:
            list[tuple[bytes, Path]]: 由 (png图像字节流, 图像本地绝对路径) 构成的元组列表。

        Raises:
            IndexError: 指定的页码越界。
        """
        # 1. 执行第一阶段：Office 转换为临时 PDF
        pdf_path = await self.convert_to_pdf(doc_path, self._default_output_dir)

        try:
            # 2. 读取 PDF 文件的总页码数以作越界防范
            total_pages = self._pdf_service.get_page_count(pdf_path)

            pages_to_render = []
            if pages is None:
                # 默认情况下生成所有页面的基于 0 的内部索引列表
                pages_to_render = list(range(total_pages))
            else:
                # 校验用户输入的 1-based 页码是否合法，并折算为 0-based 物理索引
                for p in pages:
                    if p < 1 or p > total_pages:
                        raise IndexError(
                            f"Page/slide number {p} is out of bounds (1-{total_pages})."
                        )
                    pages_to_render.append(p - 1)

            results: list[tuple[bytes, Path]] = []
            # 3. 逐页渲染指定的 PDF 页面为 PNG
            for idx in pages_to_render:
                png_bytes, file_path_str = await self._pdf_service.render_pdf_page(
                    pdf_path,
                    idx,
                    dpi=dpi,
                )
                results.append((png_bytes, Path(file_path_str)))

            return results

        finally:
            # 4. 安全防护：在 finally 块中绝对确保临时生成的 PDF 中间介质被彻底删除，防磁盘空间泄漏
            if pdf_path.is_file():
                try:
                    pdf_path.unlink()
                except Exception:
                    pass
