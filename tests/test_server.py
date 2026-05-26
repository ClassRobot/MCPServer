"""Tests for the MCP server scaffold."""

from mcp_server.app import create_server
from mcp_server.config import DatabaseSettings, ServerSettings
from mcp_server.prompts.planning import summarize_request
from mcp_server.resources.project import project_info
from mcp_server.tools.health import echo, ping


def test_ping_returns_pong() -> None:
    assert ping() == "pong"


def test_echo_returns_original_message() -> None:
    assert echo("hello") == "hello"


def test_project_info_describes_mcp_layers() -> None:
    info = project_info()

    assert "src/mcp_server/tools" in info
    assert "src/mcp_server/resources" in info
    assert "src/mcp_server/prompts" in info
    assert "src/mcp_server/services" in info


def test_prompt_contains_task() -> None:
    task = "Implement weather tool"
    assert task in summarize_request(task)


def test_create_server_uses_expected_settings() -> None:
    server = create_server(ServerSettings(name="Test Server", host="0.0.0.0", port=9000))

    assert server.name == "Test Server"
    assert server.settings.host == "0.0.0.0"
    assert server.settings.port == 9000
    assert server.settings.json_response is True


def test_create_server_hides_database_capabilities_when_database_is_disabled() -> None:
    server = create_server(ServerSettings())

    tool_names = {tool.name for tool in server._tool_manager.list_tools()}
    resource_uris = {str(resource.uri) for resource in server._resource_manager.list_resources()}

    assert "database_record_query" not in tool_names
    assert "database_list_query_history" not in tool_names
    assert "history://recent" not in resource_uris
    assert "project://info" in resource_uris


def test_create_server_registers_database_capabilities_when_database_is_enabled() -> None:
    server = create_server(
        ServerSettings(
            database=DatabaseSettings(
                enabled=True,
                sqlalchemy_url="sqlite+aiosqlite:///:memory:",
            )
        )
    )

    tool_names = {tool.name for tool in server._tool_manager.list_tools()}
    resource_uris = {str(resource.uri) for resource in server._resource_manager.list_resources()}

    assert "database_record_query" in tool_names
    assert "database_list_query_history" in tool_names
    assert "history://recent" in resource_uris
