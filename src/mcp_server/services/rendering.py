"""基于 Playwright 无头浏览器将 HTML 或 Markdown 内容转换为高清图像的业务服务层。

该模块对外提供高素质的文本栅格化渲染及基于 ECharts 数据图表生成的端到端转换服务，
利用无头浏览器强大的 CSS 渲染 and JS 执行能力，输出具有高交互和现代视觉美感的静态图片。
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import markdown

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.schemas.rendering import RenderImageResult


class ContentRenderingService:
    """内容高保真排版渲染服务类。

    协同有状态浏览器会话管理器，提供将 HTML/Markdown 原文转为高清 PNG、以及将特定指标数据绘制为精美 ECharts 统计图表的核心功能。
    """

    #: 默认全局渲染超时熔断时限（单位：秒）
    DEFAULT_RENDER_TIMEOUT_SEC = 60

    def __init__(
        self,
        session_manager: BrowserSessionManager,
        default_output_dir: Path,
        render_timeout_sec: int = DEFAULT_RENDER_TIMEOUT_SEC,
    ) -> None:
        """初始化内容高保真排版渲染服务。

        Args:
            session_manager (BrowserSessionManager): Playwright 浏览器有状态会话管理器。
            default_output_dir (Path): 默认生成的 PNG 渲染图像保存的目标目录。
            render_timeout_sec (int): 渲染时限阈值（秒），默认值为 60。
        """
        self._session_manager = session_manager
        self._default_output_dir = default_output_dir
        self._render_timeout_sec = render_timeout_sec
        # 递归初始化生成目标物理目录
        self._default_output_dir.mkdir(parents=True, exist_ok=True)

    async def render(
        self,
        content: str,
        input_format: Literal["html", "markdown"],
        theme: Literal["light", "dark"] = "light",
        width: int = 800,
        height: int | None = None,
        output_path: str | None = None,
    ) -> RenderImageResult:
        """将任意 HTML 或 Markdown 字符流高保真转换排版为 PNG 图像，并支持同步写入磁盘。

        Args:
            content (str): HTML 或 Markdown 文本内容。
            input_format (Literal["html", "markdown"]): 输入内容的格式类型。
            theme (Literal["light", "dark"]): 排版主题，支持 "light" 或 "dark"。默认值为 "light"。
            width (int): 渲染画布的视口宽度（像素），默认值为 800。
            height (int | None): 渲染画布的视口高度（像素）。若为 None，则自适应内容实际物理高度。
            output_path (str | None): 生成图像的保存路径。若未提供，则在默认输出目录下生成随机文件名。

        Returns:
            RenderImageResult: 包含文件路径、Base64 字符串、实际渲染尺寸等信息的结构化结果。

        Raises:
            RuntimeError: 渲染耗时超时，或 Playwright 驱动发生其他不可逆内核异常。
        """
        # 1. 视情况将 Markdown 解析为结构化 HTML，并套用精美的 CSS 样式系统
        if input_format == "markdown":
            html = self._wrap_markdown_in_template(content, theme=theme, width=width)
        else:
            html = content

        # 2. 拉起一个独立的无头浏览器沙箱会话进行安全隔离渲染
        session_info = await self._session_manager.create_session(headless=True)
        session_id = session_info.session_id
        try:
            # 引入全局 Timeout 安全防线，杜绝极端页面网络挂起导致主进程锁死
            screenshot_bytes, actual_height = await asyncio.wait_for(
                self._capture_screenshot(session_id, html, width, height),
                timeout=self._render_timeout_sec,
            )
        except TimeoutError as exc:
            raise RuntimeError(f"Rendering timed out after {self._render_timeout_sec}s.") from exc
        except Exception as exc:
            if not isinstance(exc, RuntimeError):
                raise RuntimeError(f"Rendering failed: {exc}") from exc
            raise
        finally:
            # 确保无论渲染如何，必须关闭底层无头浏览器标签页/句柄，防内存泄漏
            await self._session_manager.close_session(session_id)

        # 3. 确定本地持久化路径并自动处理相对/绝对转换
        if output_path:
            resolved_path = Path(output_path)
            if not resolved_path.is_absolute():
                resolved_path = self._default_output_dir / resolved_path
        else:
            resolved_path = self._default_output_dir / f"render_{uuid4().hex[:8]}.png"

        # 4. 后台执行写盘操作，通过 to_thread 将文件 I/O 卸载，保证主线程响应极速
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(resolved_path.write_bytes, screenshot_bytes)

        # 5. 同时生成 Base64 编码，方便 MCP 通道直接回传富文本图片资产
        base64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
        return RenderImageResult(
            file_path=str(resolved_path),
            base64_image=base64_data,
            width=width,
            height=actual_height,
            input_format=input_format,
        )

    async def render_chart(
        self,
        chart_type: Literal["line", "bar", "pie", "radar", "scatter"],
        data: dict[str, Any],
        title: str | None = None,
        theme: Literal["light", "dark"] = "light",
        width: int = 800,
        height: int = 600,
        output_path: str | None = None,
    ) -> RenderImageResult:
        """调用现代且功能强大的 Apache ECharts 图表引擎，将业务指标渲染为具有数字科技视觉美感的高保真图像。

        Args:
            chart_type (Literal["line", "bar", "pie", "radar", "scatter"]): 目标图表种类。
            data (dict[str, Any]): 图表渲染数据集。支持传入完全自定义的 "option" 参数字典，或包含 "labels" 及 "datasets" 的规整结构。
            title (str | None): 可选的图表标题。
            theme (Literal["light", "dark"]): 主题风格，支持 "light" 或 "dark"。默认值为 "light"。
            width (int): 生成图表的宽度（像素），默认值为 800。
            height (int): 生成图表的高度（像素），默认值为 600。
            output_path (str | None): 生成图像的保存路径。

        Returns:
            RenderImageResult: 高清图表渲染结果体。
        """
        # 1. 针对 Light/Dark 主题定制极客黑镜和雅致白金两套极高规格的 UI 色调及投影特效
        if theme == "dark":
            bg_color = "#0d1117"
            card_bg = "#161b22"
            border_color = "#30363d"
            shadow = "0 8px 32px 0 rgba(0, 0, 0, 0.5)"
            echarts_theme = "dark"
        else:
            bg_color = "#f6f8fa"
            card_bg = "#ffffff"
            border_color = "#e1e4e8"
            shadow = "0 8px 32px 0 rgba(149, 157, 165, 0.15)"
            echarts_theme = "light"

        # 2. 转换或智能装配 ECharts 特有的 Option 控制流
        if "option" in data:
            option = data["option"]
        else:
            labels = data.get("labels", [])
            datasets = data.get("datasets", [])
            series = []
            legend_data = []

            # 精选现代科技感 HSL 渐变与色彩搭配方案，规避原生刺眼红绿蓝
            if theme == "dark":
                colors = ["#4facfe", "#00f2fe", "#f35588", "#ffb13b", "#05dfd7", "#a3f7bf"]
            else:
                colors = ["#1890ff", "#2fc25b", "#facc14", "#223273", "#8543e0", "#13c2c2"]

            # 构建符合 ECharts 系列标准的 series 数组
            for i, ds in enumerate(datasets):
                ds_name = ds.get("label") or ds.get("name") or f"Dataset {i + 1}"
                legend_data.append(ds_name)
                ds_values = ds.get("data") or ds.get("values") or []

                series_item: dict[str, Any] = {
                    "name": ds_name,
                    "data": ds_values,
                }

                # 针对不同图表类型，自适应注入高规格美化参数
                if chart_type == "line":
                    series_item["type"] = "line"
                    series_item["smooth"] = True  # 采用贝塞尔三次平滑曲线，视觉极为柔和流线
                    series_item["symbolSize"] = 6
                    series_item["lineStyle"] = {"width": 3}
                    series_item["itemStyle"] = {"color": colors[i % len(colors)]}
                    # 渐变区域填充算法，从主色淡入至全透明
                    series_item["areaStyle"] = {
                        "opacity": 0.1,
                        "color": {
                            "type": "linear",
                            "x": 0,
                            "y": 0,
                            "x2": 0,
                            "y2": 1,
                            "colorStops": [
                                {"offset": 0, "color": colors[i % len(colors)]},
                                {"offset": 1, "color": "transparent"},
                            ],
                        },
                    }
                elif chart_type == "bar":
                    series_item["type"] = "bar"
                    series_item["barMaxWidth"] = 40  # 避免条数过少时柱体过宽变丑
                    series_item["itemStyle"] = {
                        "color": colors[i % len(colors)],
                        "borderRadius": [6, 6, 0, 0],  # 注入圆角微动画效果
                    }
                elif chart_type == "pie":
                    series_item["type"] = "pie"
                    series_item["radius"] = ["45%", "70%"]  # 高级环形图（甜甜圈）比例
                    series_item["avoidLabelOverlap"] = True
                    series_item["itemStyle"] = {
                        "borderRadius": 8,
                        "borderColor": "#0d1117" if theme == "dark" else "#ffffff",
                        "borderWidth": 2,
                    }
                    series_item["label"] = {
                        "show": True,
                        "position": "outside",
                        "formatter": "{b}: {c} ({d}%)",
                    }
                    pie_data = []
                    for j, val in enumerate(ds_values):
                        lbl = labels[j] if j < len(labels) else f"Item {j + 1}"
                        pie_data.append({"value": val, "name": lbl})
                    series_item["data"] = pie_data
                elif chart_type == "radar":
                    series_item["type"] = "radar"
                    series_item["symbolSize"] = 4
                    series_item["itemStyle"] = {"color": colors[i % len(colors)]}
                    series_item["areaStyle"] = {"opacity": 0.25}
                elif chart_type == "scatter":
                    series_item["type"] = "scatter"
                    series_item["symbolSize"] = 12
                    series_item["itemStyle"] = {
                        "color": colors[i % len(colors)],
                        "shadowBlur": 8,
                        "shadowColor": colors[i % len(colors)],
                    }

                series.append(series_item)

            # 装配全局通用样式树
            option = {
                "title": {
                    "text": title or "",
                    "left": "center",
                    "textStyle": {
                        "color": "#f0f6fc" if theme == "dark" else "#1f2328",
                        "fontSize": 18,
                        "fontWeight": "bold",
                    },
                },
                "tooltip": {"trigger": "item" if chart_type in ["pie", "scatter"] else "axis"},
                "legend": {
                    "data": legend_data,
                    "bottom": 10,
                    "textStyle": {"color": "#8b949e" if theme == "dark" else "#57606a"},
                },
                "grid": {
                    "top": "15%",
                    "left": "8%",
                    "right": "8%",
                    "bottom": "15%",
                    "containLabel": True,
                },
                "series": series,
            }

            # 针对直角坐标系补充轴线色泽及网格虚线
            if chart_type in ["line", "bar", "scatter"]:
                option["xAxis"] = {
                    "type": "category" if chart_type != "scatter" else "value",
                    "data": labels if chart_type != "scatter" else None,
                    "axisLine": {
                        "lineStyle": {"color": "#30363d" if theme == "dark" else "#d0d7de"}
                    },
                    "axisLabel": {"color": "#8b949e" if theme == "dark" else "#57606a"},
                }
                option["yAxis"] = {
                    "type": "value",
                    "axisLine": {
                        "lineStyle": {"color": "#30363d" if theme == "dark" else "#d0d7de"}
                    },
                    "axisLabel": {"color": "#8b949e" if theme == "dark" else "#57606a"},
                    "splitLine": {
                        "lineStyle": {"color": "#21262d" if theme == "dark" else "#f0f2f5"}
                    },
                }
            elif chart_type == "radar":
                # 计算自适应的极轴最大比例跨度
                max_val = 100.0
                for ds in datasets:
                    vals = ds.get("data") or ds.get("values") or []
                    if vals:
                        max_val = max(max_val, max(vals))

                indicators = []
                for lbl in labels:
                    indicators.append({"name": lbl, "max": int(max_val * 1.1)})

                option["radar"] = {
                    "indicator": indicators,
                    "shape": "polygon",
                    "axisName": {"color": "#8b949e" if theme == "dark" else "#57606a"},
                    "splitArea": {"show": False},
                    "splitLine": {
                        "lineStyle": {"color": "#30363d" if theme == "dark" else "#d0d7de"}
                    },
                }

        # 智能预留微量 padding 以配合外部高素质卡片阴影显示
        width_inner = width - 40
        height_inner = height - 80

        # 3. 动态组装内嵌 CDN 版 ECharts 及无动画(animation=false)秒级直出渲染骨架 HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js"></script>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    width: {width}px;
    height: {height}px;
    background-color: {bg_color};
    display: flex;
    justify-content: center;
    align-items: center;
    box-sizing: border-box;
    overflow: hidden;
  }}
  .chart-wrapper {{
    width: {width_inner}px;
    height: {height_inner}px;
    background-color: {card_bg};
    border-radius: 12px;
    border: 1px solid {border_color};
    box-shadow: {shadow};
    padding: 24px;
    box-sizing: border-box;
  }}
  #chart-container {{
    width: 100%;
    height: 100%;
  }}
</style>
</head>
<body>
<div class="chart-wrapper">
  <div id="chart-container"></div>
</div>
<script>
  (function() {{
    const chartDom = document.getElementById('chart-container');
    const myChart = echarts.init(chartDom, '{echarts_theme}');
    const option = {json.dumps(option)};
    option.animation = false; // 禁用过渡动画，防止 Playwright 捕获到处于渐变中途未绘制完的残缺帧
    myChart.setOption(option);
  }})();
</script>
</body>
</html>
"""

        # 4. 进入异步沙箱截图执行流程
        session_info = await self._session_manager.create_session(headless=True)
        session_id = session_info.session_id
        try:
            screenshot_bytes, actual_height = await asyncio.wait_for(
                self._capture_screenshot(session_id, html, width, height),
                timeout=self._render_timeout_sec,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"Chart rendering timed out after {self._render_timeout_sec}s."
            ) from exc
        except Exception as exc:
            if not isinstance(exc, RuntimeError):
                raise RuntimeError(f"Chart rendering failed: {exc}") from exc
            raise
        finally:
            await self._session_manager.close_session(session_id)

        # 5. 持久化输出并生成结果 Schema
        if output_path:
            resolved_path = Path(output_path)
            if not resolved_path.is_absolute():
                resolved_path = self._default_output_dir / resolved_path
        else:
            resolved_path = self._default_output_dir / f"chart_{uuid4().hex[:8]}.png"

        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(resolved_path.write_bytes, screenshot_bytes)

        base64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
        return RenderImageResult(
            file_path=str(resolved_path),
            base64_image=base64_data,
            width=width,
            height=actual_height,
            input_format="html",
        )

    async def _capture_screenshot(
        self,
        session_id: str,
        html: str,
        width: int,
        height: int | None,
    ) -> tuple[bytes, int]:
        """驱动底层 Playwright 会话装载骨架并在微调尺寸后截取高保真 PNG。"""
        page = await self._session_manager.get_page(session_id)

        # 设置页面初始虚拟尺寸以作首屏排版布局计算
        initial_height = height if height is not None else 600
        await page.set_viewport_size({"width": width, "height": initial_height})

        # 直接加载动态组合而成的 HTML 骨架串
        await page.set_content(html)

        # 挂起以确信外部网络字体、静态资源及 CDN 加载已完全进入网络闲置状态 (networkidle)
        await page.wait_for_load_state("load")
        await page.wait_for_load_state("networkidle")

        if height is None:
            # 高级自适应算法：自动在无头沙箱中执行 JS 查询文档的物理高度，剔除底部大面积无用白色虚空
            content_height = await page.evaluate("() => document.documentElement.scrollHeight")
            viewport_height = max(content_height, 1)
            await page.set_viewport_size({"width": width, "height": viewport_height})
            screenshot_bytes = await page.screenshot(full_page=False, type="png")
            actual_height = viewport_height
        else:
            # 强行截取满幅页面
            screenshot_bytes = await page.screenshot(full_page=True, type="png")
            actual_height = height

        return screenshot_bytes, actual_height

    def _wrap_markdown_in_template(
        self,
        md_content: str,
        theme: Literal["light", "dark"],
        width: int = 800,
    ) -> str:
        """为裸 Markdown 内容注入一套符合现代审美的 GitHub-Like 质感排版卡片及响应式字重定义。"""
        # 调用 markdown 库转换，并加载主流排版、代码高亮、精美表格等常用语法糖
        rendered_html = markdown.markdown(
            md_content,
            extensions=[
                "extra",
                "codehilite",
                "tables",
                "fenced_code",
                "nl2br",
            ],
        )

        # 调配极客灰度美学 Light 与 Dark 色阶方案
        if theme == "dark":
            bg_color = "#0d1117"
            text_color = "#c9d1d9"
            heading_color = "#f0f6fc"
            border_color = "#30363d"
            code_bg = "#161b22"
            pre_bg = "#161b22"
            blockquote_border = "#8b949e"
            table_zebra = "#161b22"
        else:
            bg_color = "#ffffff"
            text_color = "#24292e"
            heading_color = "#1f2328"
            border_color = "#e1e4e8"
            code_bg = "rgba(27,31,35,0.05)"
            pre_bg = "#f6f8fa"
            blockquote_border = "#dfe2e5"
            table_zebra = "#f6f8fa"

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: {text_color};
    background-color: {bg_color};
    margin: 0;
    padding: 40px;
    display: flex;
    justify-content: center;
  }}
  .markdown-body {{
    width: 100%;
    max-width: {width}px;
    box-sizing: border-box;
  }}
  h1, h2, h3, h4, h5, h6 {{
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    color: {heading_color};
  }}
  h1 {{ font-size: 2em; padding-bottom: .3em; border-bottom: 1px solid {border_color}; }}
  h2 {{ font-size: 1.5em; padding-bottom: .3em; border-bottom: 1px solid {border_color}; }}
  h3 {{ font-size: 1.25em; }}
  p {{ margin-top: 0; margin-bottom: 16px; }}
  pre {{
    padding: 16px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
    background-color: {pre_bg};
    border-radius: 6px;
    border: 1px solid {border_color};
  }}
  code {{
    padding: .2em .4em;
    margin: 0;
    font-size: 85%;
    background-color: {code_bg};
    border-radius: 3px;
    font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  }}
  pre code {{
    background-color: transparent;
    padding: 0;
    margin: 0;
    border-radius: 0;
  }}
  ul, ol {{
    padding-left: 2em;
    margin-top: 0;
    margin-bottom: 16px;
  }}
  blockquote {{
    padding: 0 1em;
    color: #6a737d;
    border-left: .25em solid {blockquote_border};
    margin: 0 0 16px 0;
  }}
  table {{
    border-spacing: 0;
    border-collapse: collapse;
    width: 100%;
    margin-top: 0;
    margin-bottom: 16px;
  }}
  table th, table td {{
    padding: 6px 13px;
    border: 1px solid {border_color};
  }}
  table tr {{
    background-color: {bg_color};
    border-top: 1px solid {border_color};
  }}
  table tr:nth-child(2n) {{
    background-color: {table_zebra};
  }}
</style>
</head>
<body>
<div class="markdown-body">
  {rendered_html}
</div>
</body>
</html>
"""
