"""Project information resources."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def project_info() -> str:
    """Describe the scaffold and where new capabilities should be placed."""
    return (
        "This is a Python MCP server scaffold managed by uv. "
        "Put MCP tools under src/mcp_server/tools, resources under "
        "src/mcp_server/resources, prompts under src/mcp_server/prompts, "
        "and move shared business logic into dedicated service modules as the "
        "project grows."
    )


def register_project_resources(mcp: FastMCP) -> None:
    """Register project documentation resources on the FastMCP application."""
    mcp.resource("project://info")(project_info)
