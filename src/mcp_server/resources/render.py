"""Resource definitions for accessing dynamically rendered files."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

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
        # Clean and decode the filename to prevent URL-encoded directory traversal bypasses
        decoded_name = unquote(filename)

        if (
            "/" in decoded_name
            or "\\" in decoded_name
            or ".." in decoded_name
            or decoded_name.startswith(("/", "\\"))
        ):
            raise ValueError("Directory traversal attempt detected.")

        file_path = (render_output_dir / decoded_name).resolve()

        # Prevent directory traversal attacks by verifying the path is under render_output_dir
        if not file_path.is_relative_to(render_output_dir.resolve()):
            raise ValueError("Directory traversal attempt detected.")

        if not file_path.is_file():
            raise FileNotFoundError(f"Rendered file not found: {filename}")

        # Return raw bytes to be packaged as BlobResourceContents
        return file_path.read_bytes()
