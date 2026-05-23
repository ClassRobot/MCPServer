"""Tests for the MCP server scaffold."""

from mcp_server.app import create_server
from mcp_server.config import ServerSettings
from mcp_server.prompts.planning import summarize_request
from mcp_server.resources.project import project_info
from mcp_server.tools.health import echo, ping


def test_ping_returns_pong() -> None:
    assert ping() == "pong"


def test_echo_returns_original_message() -> None:
    assert echo("hello") == "hello"


def test_project_info_mentions_uv() -> None:
    assert "uv" in project_info()


def test_prompt_contains_task() -> None:
    task = "Implement weather tool"
    assert task in summarize_request(task)


def test_create_server_uses_expected_settings() -> None:
    server = create_server(ServerSettings(name="Test Server", host="0.0.0.0", port=9000))

    assert server.name == "Test Server"
    assert server.settings.host == "0.0.0.0"
    assert server.settings.port == 9000
    assert server.settings.json_response is True
