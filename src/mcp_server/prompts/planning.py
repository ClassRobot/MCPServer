"""Prompt definitions for planning and requirement clarification."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def summarize_request(task: str) -> str:
    """Build a reusable prompt template for requirement clarification and execution planning.

    Args:
        task: The user's natural language request or a technical task description.
    """
    return (
        "You are an expert system architect and lead developer. Please analyze the following "
        "user task with extreme detail:\n\n"
        f"TASK: {task}\n\n"
        "Your analysis MUST include:\n"
        "1. **Input Analysis**: Identify all required data points and their source.\n"
        "2. **Output Specification**: Define the exact format and content of the expected result.\n"
        "3. **Technical Constraints**: List any known limitations, security concerns, "
        "or dependencies.\n"
        "4. **Step-by-Step Execution Plan**: Provide a logical sequence of actions to "
        "fulfill the request.\n"
        "5. **Validation Strategy**: How will we know the implementation is successful?\n\n"
        "Please provide a structured response."
    )


def register_planning_prompts(mcp: FastMCP) -> None:
    """Register planning-related prompts on the FastMCP application."""
    mcp.prompt(
        name="summarize_request",
        description=(
            "A high-level planning prompt to help analyze complex tasks and draft execution plans."
        ),
    )(summarize_request)
