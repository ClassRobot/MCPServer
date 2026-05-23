"""Prompt registration helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .planning import register_planning_prompts


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts exposed by this project."""
    register_planning_prompts(mcp)
