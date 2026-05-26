"""基于无头浏览器排版渲染能力的规范化输出数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RenderImageResult:
    """HTML 或 Markdown 排版栅格化渲染成功后的结构化结果类。"""

    file_path: str
    base64_image: str
    width: int
    height: int
    input_format: str
