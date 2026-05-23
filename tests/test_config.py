"""Tests for configuration loading and validation."""

from __future__ import annotations

import pytest

from mcp_server.config import DEFAULT_SERVER_NAME, load_server_settings


def test_load_server_settings_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_SERVER_NAME", raising=False)
    monkeypatch.delenv("MCP_SERVER_PORT", raising=False)

    settings = load_server_settings()

    assert settings.name == DEFAULT_SERVER_NAME
    assert settings.port == 8000


def test_load_server_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_SERVER_NAME", "Workspace Server")
    monkeypatch.setenv("MCP_SERVER_PORT", "8100")

    settings = load_server_settings()

    assert settings.name == "Workspace Server"
    assert settings.port == 8100


def test_load_server_settings_rejects_invalid_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_PORT", "abc")

    with pytest.raises(ValueError, match="MCP_SERVER_PORT must be an integer"):
        load_server_settings()


def test_parse_bool_supports_numeric_and_string_values() -> None:
    from mcp_server.config import _parse_bool

    # Test boolean values
    assert _parse_bool("test", True) is True
    assert _parse_bool("test", False) is False

    # Test numeric values
    assert _parse_bool("test", 1) is True
    assert _parse_bool("test", 0) is False
    assert _parse_bool("test", 1.0) is True
    assert _parse_bool("test", 0.0) is False

    # Test string values
    assert _parse_bool("test", "true") is True
    assert _parse_bool("test", "1") is True
    assert _parse_bool("test", "yes") is True
    assert _parse_bool("test", "on") is True
    assert _parse_bool("test", "false") is False
    assert _parse_bool("test", "0") is False
    assert _parse_bool("test", "no") is False
    assert _parse_bool("test", "off") is False

    # Test invalid values
    with pytest.raises(ValueError, match="must be a boolean value"):
        _parse_bool("test", "invalid")
    with pytest.raises(ValueError, match="must be a boolean value"):
        _parse_bool("test", [])
