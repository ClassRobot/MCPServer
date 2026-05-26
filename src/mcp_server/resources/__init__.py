"""MCP 静态资源(Resources)的全局注册入口。"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.services.query_history import QueryHistoryService

from .project import register_project_resources
from .render import register_render_resources


def register_resources(
    mcp: FastMCP,
    *,
    query_history_service: QueryHistoryService,
    render_output_dir: Path,
) -> None:
    """向给定的 FastMCP 实例注册本项目暴露的所有静态资源路由。

    Args:
        mcp (FastMCP): 待注册资源路由的 FastMCP 应用实例。
        query_history_service (QueryHistoryService): 检索查询历史的持久化业务服务。
        render_output_dir (Path): 缓存渲染图像输出的目标物理路径。
    """
    register_project_resources(mcp, query_history_service=query_history_service)
    register_render_resources(mcp, render_output_dir=render_output_dir)
