"""基于 Playwright 无头浏览器及 Apache ECharts 数据可视化引擎执行高保真排版图像渲染的 MCP 工具接口层。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.rendering import ContentRenderingService
from mcp_server.tool_logging import log_mcp_tool


def register_rendering_tools(
    mcp: FastMCP,
    *,
    rendering_service: ContentRenderingService,
    logging_settings: LoggingSettings,
) -> None:
    """在 FastMCP 实例上注册内容排版及图表可视化渲染工具。

    Args:
        mcp (FastMCP): FastMCP 服务应用程序实例。
        rendering_service (ContentRenderingService): Markdown/HTML 栅格化排版渲染及 ECharts 图表生成服务。
        logging_settings (LoggingSettings): 全局日志记录审计配置。
    """

    @mcp.tool(
        name="render_content_to_image",
        description=(
            "Convert raw HTML or Markdown content into a high-fidelity PNG image. "
            "Useful for visualizing complex layouts, formatted text, or previewing web content "
            "directly within the AI conversation."
        ),
    )
    @log_mcp_tool("render_content_to_image", logging_settings)
    async def render_content_to_image(
        content: str,
        input_format: Literal["html", "markdown"],
        theme: Literal["light", "dark"] = "light",
        width: int = 800,
        height: int | None = None,
        output_path: str | None = None,
    ) -> list[Any]:
        """将指定的 HTML 或 Markdown 裸文本段落高保真排版渲染为高清 PNG 预览图。

        Args:
            content (str): HTML 或 Markdown 原始文本串。
            input_format (Literal["html", "markdown"]): 输入文本的物理格式。
            theme (Literal["light", "dark"]): 视觉风格主题，支持 'light' 或 'dark'。默认值为 'light'。
            width (int): 渲染视口像素宽度，默认值为 800。
            height (int | None): 渲染视口像素高度。若为 None 则自适应内容实际物理高度。
            output_path (str | None): 可选的实体 PNG 文件保存路径。

        Returns:
            list[Any]: 包含说明、动态资源 URI 路径及 Base64 编码图像数据的 MCP 混合资产列表。
        """
        from mcp.types import ImageContent, TextContent

        # 调用排版渲染服务执行端到端无头截图
        result = await rendering_service.render(
            content=content,
            input_format=input_format,
            theme=theme,
            width=width,
            height=height,
            output_path=output_path,
        )

        description = (
            f"Successfully rendered {input_format} content to image.\n"
            f"Dimensions: {result.width}x{result.height}px\n"
            f"Resource URI: render://{Path(result.file_path).name}"
        )

        return [
            TextContent(type="text", text=description),
            ImageContent(
                type="image",
                data=result.base64_image,
                mimeType="image/png",
            ),
        ]

    @mcp.tool(
        name="render_data_chart",
        description=(
            "Generate professional data visualizations (line, bar, pie, radar, scatter) as "
            "high-quality PNG images using Apache ECharts. "
            "Perfect for presenting data insights visually to the user."
        ),
    )
    @log_mcp_tool("render_data_chart", logging_settings)
    async def render_data_chart(
        chart_type: Literal["line", "bar", "pie", "radar", "scatter"],
        data: dict[str, Any],
        title: str | None = None,
        theme: Literal["light", "dark"] = "light",
        width: int = 800,
        height: int = 600,
        output_path: str | None = None,
    ) -> list[Any]:
        """使用现代 Apache ECharts 可视化引擎绘制极高画质的折线/柱状/饼图/雷达/散点图。

        Args:
            chart_type (Literal["line", "bar", "pie", "radar", "scatter"]): 目标图表种类。
            data (dict[str, Any]): 包含 labels 及 datasets 的结构化数据或完全自定义的 option 选项字典。
            title (str | None): 图表的顶部主标题。
            theme (Literal["light", "dark"]): 主题美学风格，支持 'light' 或 'dark'。
            width (int): 生成图像宽度，默认值为 800。
            height (int): 生成图像高度，默认值为 600。
            output_path (str | None): 可选的实体 PNG 文件保存路径。

        Returns:
            list[Any]: 包含说明、动态资源 URI 路径及 Base64 编码图像数据的 MCP 混合资产列表。
        """
        from mcp.types import ImageContent, TextContent

        # 调用图表生成服务进行渲染截图
        result = await rendering_service.render_chart(
            chart_type=chart_type,
            data=data,
            title=title,
            theme=theme,
            width=width,
            height=height,
            output_path=output_path,
        )

        description = (
            f"Successfully generated {chart_type} chart: {title or 'Untitled'}\n"
            f"Dimensions: {result.width}x{result.height}px\n"
            f"Resource URI: render://{Path(result.file_path).name}"
        )

        return [
            TextContent(type="text", text=description),
            ImageContent(
                type="image",
                data=result.base64_image,
                mimeType="image/png",
            ),
        ]
