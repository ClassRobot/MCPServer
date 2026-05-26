"""MCP 服务端的命令行 CLI 启动入口。

提供解析命令行参数、配置初始化日志系统、根据用户指定的传输协议（Transport）
拉起并运行 FastMCP 服务实例的功能。
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import replace

from .app import create_server
from .config import ServerSettings, TransportName, load_server_settings
from .logging_config import configure_logging, log_event

# 初始化当前模块的日志记录器
LOGGER = logging.getLogger(__name__)


def parse_args(
    argv: Sequence[str] | None = None,
    default_settings: ServerSettings | None = None,
) -> argparse.Namespace:
    """解析服务启动所需的命令行参数。

    Args:
        argv (Sequence[str] | None): 待解析的命令行参数列表，若为 None 则默认解析 sys.argv。
        default_settings (ServerSettings | None): 基础配置对象，用于为参数提供默认回退值。

    Returns:
        argparse.Namespace: 包含已解析参数的命名空间对象（transport, host, port）。
    """
    settings = default_settings or load_server_settings()
    parser = argparse.ArgumentParser(description="运行 MCP 服务器主程序。")
    
    # 核心通道协议参数（Stdio 模式或 HTTP 流模式）
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http", "sse"),
        default="stdio",
        help="MCP 服务器所使用的传输层协议通道，默认为 stdio。",
    )
    
    # HTTP 服务端绑定主机名
    parser.add_argument(
        "--host",
        default=settings.host,
        help="基于 HTTP 传输时的服务绑定监听主机地址。",
    )
    
    # HTTP 服务端绑定端口
    parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help="基于 HTTP 传输时的服务绑定监听端口。",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> None:
    """配置日志、解析命令行，并驱动 MCP 服务运行的核心入口。

    Args:
        argv (Sequence[str] | None): 命令行启动参数。
    """
    # 1. 载入全局服务器配置并配置日志文件及轮转器
    base_settings = load_server_settings()
    configure_logging(base_settings.logging)
    
    # 2. 解析传入的命令行输入，动态覆盖主机及端口号
    args = parse_args(argv=argv, default_settings=base_settings)
    server = create_server(replace(base_settings, host=args.host, port=args.port))
    
    transport: TransportName = args.transport
    log_event(
        LOGGER,
        logging.INFO,
        "server.run",
        transport=transport,
        host=args.host,
        port=args.port,
    )

    # 3. 根据指定的通道协议，路由到对应的服务拉起逻辑
    if transport == "stdio":
        # Stdio 标准输入输出通常用于 Claude Desktop 等客户端在本地直接以子进程拉起运行
        server.run()
        return

    # 基于 HTTP (Streamable-HTTP 或 SSE) 流模式运行，供外部客户端跨网络进行长连接调用
    server.run(transport=transport)


if __name__ == "__main__":
    main()
