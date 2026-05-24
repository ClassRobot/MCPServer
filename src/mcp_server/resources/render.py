"""Resource definitions for accessing dynamically rendered files."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP


def register_render_resources(mcp: FastMCP, render_output_dir: Path) -> None:
    """Register dynamic render resource templates on the FastMCP application."""

    @mcp.resource("render://{filename}")
    async def get_rendered_file(filename: str) -> bytes:
        """Retrieve a visually rendered file (image/PDF page/chart) over the network.

        Args:
            filename: The base name of the generated file in the render directory.

        Returns:
            The raw file content bytes, serialized as a dynamic binary resource.
        """
        # Clean the filename: check for traversal components explicitly
        if "/" in filename or "\\" in filename or ".." in filename or filename.startswith(("/", "\\")):
            raise ValueError("Directory traversal attempt detected.")

        file_path = (render_output_dir / filename).resolve()

        # Prevent directory traversal attacks by verifying the path is under render_output_dir
        if not file_path.is_relative_to(render_output_dir.resolve()):
            raise ValueError("Directory traversal attempt detected.")

        if not file_path.is_file():
            raise FileNotFoundError(f"Rendered file not found: {filename}")

        # Return raw bytes to be packaged as BlobResourceContents
        return file_path.read_bytes()
