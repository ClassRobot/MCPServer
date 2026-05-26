"""项目的基础说明文档及近期的动态历史数据资源定义。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.services.query_history import QueryHistoryService


def project_info() -> str:
    """提供描述本项目代码骨架及后续扩展规约的静态说明资源。

    Returns:
        str: 骨架结构与工具/资源/提示词扩展目录规范的只读文本。
    """
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
    """在 FastMCP 实例上注册项目元信息及近期的动态查询历史记录资源路由。

    Args:
        mcp (FastMCP): 待注册资源路由的 FastMCP 应用实例。
        query_history_service (QueryHistoryService): 检索查询历史的持久化业务服务。
    """
    mcp.resource("project://info")(project_info)

    @mcp.resource("history://recent")
    async def recent_history() -> str:
        """从关系型数据库中获取并格式化最新的 20 条网页检索历史。

        Returns:
            str: 格式化为 Markdown 清单的历史检索条目。
        """
        # 从数据库中拉取最新的 20 条搜索记录
        records = await query_history_service.list_recent_queries(limit=20)
        if not records:
            return "No query history found."

        lines = ["## Recent Query History", ""]
        # 逐条拼接显示细节：搜索内容、引擎类型、触发工具、写入时间及可选批注
        for record in records:
            lines.append(
                f"- **{record.query}** (via {record.provider}, tool: {record.source_tool})"
            )
            lines.append(f"  *Time: {record.created_at}*")
            if record.notes:
                lines.append(f"  *Notes: {record.notes}*")
        return "\n".join(lines)
