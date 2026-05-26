"""用于客户端连接及基础链路诊断的健康检查工具定义。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.tool_logging import log_mcp_tool


def ping() -> str:
    """提供极简的心跳检查返回串以验证 MCP 服务端是否处于存活状态。

    Returns:
        str: 固定的 "pong" 响应。
    """
    return "pong"


def echo(message: str) -> str:
    """提供端到端的链路回路诊断，返回客户端原样发送的输入信息。

    Args:
        message (str): 待回显输出的原始文本。

    Returns:
        str: 原样回显的文本信息。
    """
    return message


def register_health_tools(
    mcp: FastMCP,
    *,
    logging_settings: LoggingSettings,
) -> None:
    """注册最基础的在线探针与端到端链路回显调试工具。

    Args:
        mcp (FastMCP): FastMCP 服务应用程序实例。
        logging_settings (LoggingSettings): 全局日志记录审计配置。
    """
    mcp.tool(
        name="ping",
        description="A minimal heartbeat tool to check if the MCP server is responsive.",
    )(log_mcp_tool("ping", logging_settings)(ping))

    mcp.tool(
        name="echo",
        description="A diagnostic tool that echoes back the input message to verify connectivity.",
    )(log_mcp_tool("echo", logging_settings)(echo))
