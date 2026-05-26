"""与关系型数据库持久化交互相关的 MCP 工具接口定义。"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.services.query_history import QueryHistoryService
from mcp_server.tool_logging import log_mcp_tool


def register_database_tools(
    mcp: FastMCP,
    *,
    query_history_service: QueryHistoryService,
    logging_settings: LoggingSettings,
) -> None:
    """注册用于录入及调取底层数据库查询历史记录的 MCP 工具。

    Args:
        mcp (FastMCP): FastMCP 服务应用程序实例。
        query_history_service (QueryHistoryService): 检索查询历史记录持久化服务。
        logging_settings (LoggingSettings): 全局日志记录审计配置。
    """

    @mcp.tool(
        name="database_record_query",
        description=(
            "Permanently record a search query and its metadata into the persistent database. "
            "Useful for auditing, history tracking, and future query optimization."
        ),
    )
    @log_mcp_tool("database_record_query", logging_settings)
    async def database_record_query(
        query: str,
        provider: str = "manual",
        source_tool: str = "manual",
        notes: str | None = None,
    ) -> list[Any]:
        """向关系型数据库持久化录入一条检索历史记录。

        Args:
            query (str): 被检索的原始用户提示词短语。
            provider (str): 搜索引擎名称标识，默认值为 "manual"。
            source_tool (str): 写入该条记录的触发工具标识，默认值为 "manual"。
            notes (str | None): 可选的补充元数据或上下文关联备注。

        Returns:
            list[Any]: MCP 包装好的成功确认文本。
        """
        from mcp.types import TextContent

        # 调用领域服务持久化数据
        record = await query_history_service.record_query(
            query=query,
            provider=provider,
            source_tool=source_tool,
            notes=notes,
        )
        return [
            TextContent(
                type="text",
                text=f"Successfully recorded query (ID: {record.id}) at {record.created_at}",
            )
        ]

    @mcp.tool(
        name="database_list_query_history",
        description=(
            "Retrieve a list of the most recent query records from the database. "
            "Allows the AI to see past interactions and maintain context over time."
        ),
    )
    @log_mcp_tool("database_list_query_history", logging_settings)
    async def database_list_query_history(limit: int = 10) -> list[Any]:
        """从数据库拉取最新的若干条搜索记录，并拼装为易读清单。

        Args:
            limit (int): 返回结果的最大历史记录限制，默认值为 10。

        Returns:
            list[Any]: MCP 包装好的历史排版文本清单。
        """
        from mcp.types import TextContent

        records = await query_history_service.list_recent_queries(limit=limit)
        if not records:
            return [TextContent(type="text", text="No query history found.")]

        lines = [f"Showing last {len(records)} query records:", ""]
        # 逐条拼接显示时间、搜索词及提供商
        for record in records:
            lines.append(f"- [{record.created_at}] {record.query} ({record.provider})")

        return [TextContent(type="text", text="\n".join(lines))]
