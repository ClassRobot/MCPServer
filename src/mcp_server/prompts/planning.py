"""Prompt definitions for planning and requirement clarification."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def summarize_request(task: str) -> str:
    """Build a reusable prompt template for requirement clarification."""
    return (
        "Please analyze the following task, identify the expected inputs, outputs, "
        f"and implementation constraints, then provide a clear execution plan:\n\n{task}"
    )


def register_planning_prompts(mcp: FastMCP) -> None:
    """Register planning-related prompts on the FastMCP application."""
    mcp.prompt()(summarize_request)
