"""Tests for the CLI entrypoint."""

from mcp_server.__main__ import parse_args
from mcp_server.config import ServerSettings


def test_parse_args_uses_config_defaults() -> None:
    args = parse_args([], default_settings=ServerSettings(host="0.0.0.0", port=9100))

    assert args.transport == "stdio"
    assert args.host == "0.0.0.0"
    assert args.port == 9100


def test_parse_args_accepts_runtime_overrides() -> None:
    args = parse_args(
        ["--transport", "streamable-http", "--host", "127.0.0.2", "--port", "9200"],
    )

    assert args.transport == "streamable-http"
    assert args.host == "127.0.0.2"
    assert args.port == 9200
