"""MCP 提示词(Prompts)模板的全局注册入口。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .planning import register_planning_prompts


def register_prompts(mcp: FastMCP) -> None:
    """向给定的 FastMCP 实例注册本项目暴露的所有提示词模板。

    Args:
        mcp (FastMCP): 待绑定注册提示词模板的 FastMCP 实例。
    """
    register_planning_prompts(mcp)
