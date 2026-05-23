"""Configuration models and loaders for the MCP server scaffold."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

TransportName = Literal["stdio", "sse", "streamable-http"]

DEFAULT_SERVER_NAME = "MCP Server"
DEFAULT_SERVER_INSTRUCTIONS = (
    "A starter MCP server scaffold. Extend this server with project-specific "
    "tools, resources, and prompts."
)


@dataclass(frozen=True, slots=True)
class ServerSettings:
    """Stable server settings shared by the CLI and application factory."""

    name: str = DEFAULT_SERVER_NAME
    instructions: str = DEFAULT_SERVER_INSTRUCTIONS
    host: str = "127.0.0.1"
    port: int = 8000
    mount_path: str = "/"
    streamable_http_path: str = "/mcp"
    json_response: bool = True
    stateless_http: bool = True


def load_server_settings() -> ServerSettings:
    """Load server settings from environment variables with validated defaults."""
    return ServerSettings(
        name=os.getenv("MCP_SERVER_NAME", DEFAULT_SERVER_NAME),
        instructions=os.getenv("MCP_SERVER_INSTRUCTIONS", DEFAULT_SERVER_INSTRUCTIONS),
        host=os.getenv("MCP_SERVER_HOST", "127.0.0.1"),
        port=_read_positive_int_env("MCP_SERVER_PORT", 8000),
        mount_path=os.getenv("MCP_SERVER_MOUNT_PATH", "/"),
        streamable_http_path=os.getenv("MCP_SERVER_STREAMABLE_HTTP_PATH", "/mcp"),
    )


def _read_positive_int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment for runtime settings."""
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}.") from exc

    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer, got {parsed}.")
    return parsed
