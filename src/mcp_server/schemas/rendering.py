"""Structured schema for image rendering capabilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RenderImageResult:
    """The structured result returned by the image rendering tool."""

    file_path: str
    base64_image: str
    width: int
    height: int
    input_format: str
