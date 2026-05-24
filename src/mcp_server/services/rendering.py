"""Service layer for converting HTML or Markdown to high-quality images using Playwright."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Literal
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
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"Rendering timed out after {self._render_timeout_sec}s."
            ) from exc
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
        self, md_content: str, theme: Literal["light", "dark"], width: int = 800,
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
