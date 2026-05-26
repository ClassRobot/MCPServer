"""访问动态渲染出的文件（图像、PDF 栅格化页面及图表）的静态资源路径定义。"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from mcp.server.fastmcp import FastMCP


def register_render_resources(mcp: FastMCP, render_output_dir: Path) -> None:
    """在 FastMCP 实例上注册动态图像及 PDF 资源调取的模板路由。

    Args:
        mcp (FastMCP): 待注册资源路由的 FastMCP 应用实例。
        render_output_dir (Path): 缓存渲染图像输出的目标物理路径。
    """

    @mcp.resource("render://{filename}")
    async def get_rendered_file(filename: str) -> bytes:
        """根据文件名从网络端直接调取高保真渲染的原始二进制文件内容（如 PNG 图片）。

        Args:
            filename (str): 在渲染输出目录中已生成好的资产文件名。

        Returns:
            bytes: 文件的原始二进制字节流，以 Blob 资源形式传回客户端。

        Raises:
            ValueError: 检测到利用非法路径字符（如 /、\\、..）发起的目录遍历安全攻击。
            FileNotFoundError: 对应的渲染文件在指定资产目录下不存在。
        """
        # 1. 对 URL 编码过的文件名进行净化解码，防范特定编码下的目录穿越
        decoded_name = unquote(filename)

        # 2. 强安全屏障拦截：禁止任何包含反斜杠、斜杠及父目录标识的恶意遍历串
        if (
            "/" in decoded_name
            or "\\" in decoded_name
            or ".." in decoded_name
            or decoded_name.startswith(("/", "\\"))
        ):
            raise ValueError("Directory traversal attempt detected.")

        file_path = (render_output_dir / decoded_name).resolve()

        # 3. 双重安全防线：通过计算相对归属，物理层面上绝对杜绝跨越 render_output_dir 的目录安全溢出
        if not file_path.is_relative_to(render_output_dir.resolve()):
            raise ValueError("Directory traversal attempt detected.")

        if not file_path.is_file():
            raise FileNotFoundError(f"Rendered file not found: {filename}")

        # 4. 读取原始字节以 BlobResourceContents 形式通过 MCP 管道回传
        return file_path.read_bytes()
