"""Project information resources."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.services.query_history import QueryHistoryService


def project_info() -> str:
    """Describe the scaffold and where new capabilities should be placed."""
    return (
        "This is a Python MCP server scaffold managed by uv. "
        "Put MCP tools under src/mcp_server/tools, resources under "
        "src/mcp_server/resources, prompts under src/mcp_server/prompts, "
        "and move shared business logic into dedicated service modules as the "
        "project grows."
    )


def register_project_resources(
    mcp: FastMCP,
    *,
    query_history_service: QueryHistoryService,
) -> None:
    """Register project documentation and dynamic history resources on the FastMCP application."""
    mcp.resource("project://info")(project_info)

    @mcp.resource("history://recent")
    async def recent_history() -> str:
        """Fetch and format the most recent search query history."""
        records = await query_history_service.list_recent_queries(limit=20)
        if not records:
            return "No query history found."

        lines = ["## Recent Query History", ""]
        for record in records:
            lines.append(
                f"- **{record.query}** (via {record.provider}, tool: {record.source_tool})"
            )
            lines.append(f"  *Time: {record.created_at}*")
            if record.notes:
                lines.append(f"  *Notes: {record.notes}*")
        return "\n".join(lines)
