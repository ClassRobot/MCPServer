"""Public server exports for the MCP server scaffold."""

from __future__ import annotations

from .app import create_server

server = create_server()

__all__ = ["create_server", "server"]
