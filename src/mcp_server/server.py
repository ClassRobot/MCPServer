"""MCP 服务端独立运行时的全局实例导出。

本模块默认实例化并导出了一个全局单例的 FastMCP 服务对象，
可作为第三方 ASGI 服务器（如 uvicorn 命令行）拉起运行的入口点。
"""

from __future__ import annotations

from .app import create_server

# 默认实例化全局服务器实例
server = create_server()

__all__ = ["create_server", "server"]
