"""CLI entrypoint for the MCP server."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import replace

from .app import create_server
from .config import ServerSettings, TransportName, load_server_settings
from .logging_config import configure_logging, log_event

LOGGER = logging.getLogger(__name__)


def parse_args(
    argv: Sequence[str] | None = None,
    default_settings: ServerSettings | None = None,
) -> argparse.Namespace:
    """Parse command line arguments for the server runner."""
    settings = default_settings or load_server_settings()
    parser = argparse.ArgumentParser(description="Run the MCP server scaffold.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http", "sse"),
        default="stdio",
        help="Transport used by the MCP server.",
    )
    parser.add_argument(
        "--host",
        default=settings.host,
        help="Host used by HTTP-based transports.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help="Port used by HTTP-based transports.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the MCP server using the selected transport."""
    base_settings = load_server_settings()
    configure_logging(base_settings.logging)
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

    if transport == "stdio":
        server.run()
        return

    server.run(transport=transport)


if __name__ == "__main__":
    main()
