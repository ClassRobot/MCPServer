"""Service layer for converting HTML or Markdown to high-quality images using Playwright."""

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
    """Orchestrate conversion of HTML and Markdown strings to images using browser automation."""

    #: Default timeout for the entire rendering pipeline (seconds).
    DEFAULT_RENDER_TIMEOUT_SEC = 60

    def __init__(
        self,
        session_manager: BrowserSessionManager,
        default_output_dir: Path,
        render_timeout_sec: int = DEFAULT_RENDER_TIMEOUT_SEC,
    ) -> None:
        self._session_manager = session_manager
        self._default_output_dir = default_output_dir
        self._render_timeout_sec = render_timeout_sec
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
        """Render HTML or Markdown content to a PNG image and optionally save it to disk."""
        # Convert Markdown to HTML and wrap with CSS if requested
        if input_format == "markdown":
            html = self._wrap_markdown_in_template(content, theme=theme, width=width)
        else:
            html = content

        # Create a temporary browser session
        session_info = await self._session_manager.create_session(headless=True)
        session_id = session_info.session_id
        try:
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
            await self._session_manager.close_session(session_id)

        # Determine target file path
        if output_path:
            resolved_path = Path(output_path)
            if not resolved_path.is_absolute():
                resolved_path = self._default_output_dir / resolved_path
        else:
            resolved_path = self._default_output_dir / f"render_{uuid4().hex[:8]}.png"

        # Safe non-blocking file write using threadpool
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(resolved_path.write_bytes, screenshot_bytes)

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
        """Render a premium data chart using Apache ECharts and Playwright screenshot."""
        # Setup aesthetic color palettes and HSL options
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

        # Build ECharts option structure
        if "option" in data:
            option = data["option"]
        else:
            labels = data.get("labels", [])
            datasets = data.get("datasets", [])
            series = []
            legend_data = []

            # Curated harmonious premium color palette
            if theme == "dark":
                colors = ["#4facfe", "#00f2fe", "#f35588", "#ffb13b", "#05dfd7", "#a3f7bf"]
            else:
                colors = ["#1890ff", "#2fc25b", "#facc14", "#223273", "#8543e0", "#13c2c2"]

            for i, ds in enumerate(datasets):
                ds_name = ds.get("label") or ds.get("name") or f"Dataset {i + 1}"
                legend_data.append(ds_name)
                ds_values = ds.get("data") or ds.get("values") or []

                series_item: dict[str, Any] = {
                    "name": ds_name,
                    "data": ds_values,
                }

                if chart_type == "line":
                    series_item["type"] = "line"
                    series_item["smooth"] = True
                    series_item["symbolSize"] = 6
                    series_item["lineStyle"] = {"width": 3}
                    series_item["itemStyle"] = {"color": colors[i % len(colors)]}
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
                    series_item["barMaxWidth"] = 40
                    series_item["itemStyle"] = {
                        "color": colors[i % len(colors)],
                        "borderRadius": [6, 6, 0, 0],
                    }
                elif chart_type == "pie":
                    series_item["type"] = "pie"
                    series_item["radius"] = ["45%", "70%"]
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

        width_inner = width - 40
        height_inner = height - 80

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
    option.animation = false;
    myChart.setOption(option);
  }})();
</script>
</body>
</html>
"""

        # Create a temporary browser session and take screen snapshot
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

        # Resolve local disk output path
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
        """Run the core Playwright rendering pipeline and return (png_bytes, actual_height)."""
        page = await self._session_manager.get_page(session_id)

        # Configure initial viewport size for layout calculation
        initial_height = height if height is not None else 600
        await page.set_viewport_size({"width": width, "height": initial_height})

        # Set HTML content directly
        await page.set_content(html)

        # Wait for content to render (fonts, styles, external dependencies)
        await page.wait_for_load_state("load")
        await page.wait_for_load_state("networkidle")

        if height is None:
            # Auto-detect exact content height to avoid bottom whitespace
            content_height = await page.evaluate("() => document.documentElement.scrollHeight")
            viewport_height = max(content_height, 1)
            await page.set_viewport_size({"width": width, "height": viewport_height})
            screenshot_bytes = await page.screenshot(full_page=False, type="png")
            actual_height = viewport_height
        else:
            screenshot_bytes = await page.screenshot(full_page=True, type="png")
            actual_height = height

        return screenshot_bytes, actual_height

    def _wrap_markdown_in_template(
        self,
        md_content: str,
        theme: Literal["light", "dark"],
        width: int = 800,
    ) -> str:
        """Wrap markdown body inside a premium structured HTML shell with harmonious stylesheet."""
        # Render markdown content
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

        # Style sheet definition
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
