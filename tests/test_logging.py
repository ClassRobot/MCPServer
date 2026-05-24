"""Tests for project logging configuration and MCP tool call logs."""

from __future__ import annotations

import logging
import re
from io import StringIO
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from mcp_server.config import LoggingSettings, load_server_settings
from mcp_server.logging_config import configure_logging, log_event
from mcp_server.tool_logging import log_mcp_tool

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


@pytest.fixture(autouse=True)
def restore_logging_handlers() -> None:
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    yield

    for handler in list(root_logger.handlers):
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
            handler.close()
    for handler in original_handlers:
        if handler not in root_logger.handlers:
            root_logger.addHandler(handler)
    root_logger.setLevel(original_level)


def test_load_server_settings_reads_logging_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "logging.yaml"
    config_path.write_text(
        "\n".join(
            [
                "level: DEBUG",
                "console:",
                "  enabled: false",
                "  color: false",
                "file:",
                "  enabled: true",
                "  path: runtime/custom.log",
                "  retention_days: 30",
                "tool:",
                "  args_enabled: true",
                "  max_field_length: 24",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("MCP_LOGGING_CONFIG_PATH", str(config_path))

    settings = load_server_settings()

    assert settings.logging_config_path == config_path
    assert settings.logging.level == "DEBUG"
    assert settings.logging.console_enabled is False
    assert settings.logging.console_color_enabled is False
    assert settings.logging.file_enabled is True
    assert settings.logging.file_path == tmp_path / "runtime" / "custom.log"
    assert settings.logging.retention_days == 30
    assert settings.logging.tool_args_enabled is True
    assert settings.logging.max_field_length == 24


def test_logging_environment_overrides_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "logging.yaml"
    config_path.write_text("level: INFO\nfile:\n  retention_days: 14\n", encoding="utf-8")
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("MCP_LOGGING_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("MCP_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("MCP_LOG_CONSOLE_COLOR", "false")
    monkeypatch.setenv("MCP_LOG_FILE_PATH", "logs/override.log")
    monkeypatch.setenv("MCP_LOG_RETENTION_DAYS", "7")

    settings = load_server_settings()

    assert settings.logging.level == "ERROR"
    assert settings.logging.console_color_enabled is False
    assert settings.logging.file_path == tmp_path / "logs" / "override.log"
    assert settings.logging.retention_days == 7


def test_load_server_settings_rejects_invalid_log_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "logging.yaml"
    config_path.write_text("level: TRACE\n", encoding="utf-8")
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("MCP_LOGGING_CONFIG_PATH", str(config_path))

    with pytest.raises(ValueError, match="MCP_LOG_LEVEL must be one of"):
        load_server_settings()


def test_configure_logging_writes_stderr_and_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_path = tmp_path / "logs" / "mcp-server.log"
    configure_logging(LoggingSettings(file_path=log_path))

    log_event(
        logging.getLogger("mcp_server.tests"),
        logging.INFO,
        "test.event",
        sample="hello world",
    )

    captured = capsys.readouterr()
    file_logs = log_path.read_text(encoding="utf-8")

    assert captured.out == ""
    assert "\x1b[" in captured.err
    assert '[INFO] mcp_server | event=test.event sample="hello world"' in strip_ansi(captured.err)
    assert "\x1b[" not in file_logs
    assert "event=test.event" in file_logs


def test_configure_logging_can_disable_console_color(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_path = tmp_path / "logs" / "mcp-server.log"
    configure_logging(
        LoggingSettings(
            console_color_enabled=False,
            file_path=log_path,
        )
    )

    log_event(logging.getLogger("mcp_server.tests"), logging.INFO, "plain.event")

    captured = capsys.readouterr()

    assert "\x1b[" not in captured.err
    assert "[INFO] mcp_server | event=plain.event" in captured.err


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "mcp-server.log"
    settings = LoggingSettings(console_enabled=False, file_path=log_path)
    logger = logging.getLogger("mcp_server.tests")

    configure_logging(settings)
    configure_logging(settings)
    log_event(logger, logging.INFO, "single.event")

    lines = log_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert "event=single.event" in lines[0]


def test_configure_logging_removes_existing_root_handlers(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    foreign_stream = StringIO()
    foreign_handler = logging.StreamHandler(foreign_stream)
    foreign_handler.setFormatter(logging.Formatter("foreign:%(message)s"))
    logging.getLogger().addHandler(foreign_handler)

    configure_logging(LoggingSettings(file_path=tmp_path / "mcp-server.log"))
    logging.getLogger("mcp.server.streamable_http").info("Terminating session: None")

    captured = capsys.readouterr()

    assert foreign_stream.getvalue() == ""
    assert "[INFO] mcp | Terminating session: None" in strip_ansi(captured.err)


def test_configure_logging_uses_daily_file_rotation(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "mcp-server.log"
    configure_logging(
        LoggingSettings(
            console_enabled=False,
            file_path=log_path,
            retention_days=14,
        )
    )

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, TimedRotatingFileHandler)
    ]

    assert len(handlers) == 1
    assert handlers[0].when == "MIDNIGHT"
    assert handlers[0].backupCount == 14


def test_configure_logging_overrides_uvicorn_log_config(tmp_path: Path) -> None:
    import uvicorn.config

    log_path = tmp_path / "logs" / "mcp-server.log"
    configure_logging(LoggingSettings(file_path=log_path))

    log_config = uvicorn.config.LOGGING_CONFIG

    assert log_config["formatters"]["console"] == {
        "()": "mcp_server.logging_config.KeyValueFormatter",
        "use_colors": True,
    }
    assert log_config["formatters"]["file"] == {
        "()": "mcp_server.logging_config.KeyValueFormatter",
        "use_colors": False,
    }
    assert log_config["handlers"]["default"]["formatter"] == "console"
    assert log_config["handlers"]["default"]["stream"] == "ext://sys.stderr"
    assert log_config["handlers"]["file"]["formatter"] == "file"
    assert log_config["handlers"]["file"]["filename"] == str(log_path)
    assert log_config["loggers"]["uvicorn.access"]["handlers"] == ["default", "file"]
    assert log_config["loggers"]["uvicorn.access"]["propagate"] is False


@pytest.mark.asyncio
async def test_tool_logging_records_success_without_default_args(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "tools.log"
    settings = LoggingSettings(console_enabled=False, file_path=log_path)
    configure_logging(settings)

    @log_mcp_tool("sample_tool", settings)
    async def sample_tool(secret_token: str, content: str) -> str:
        return "ok"

    result = await sample_tool("hidden", "large input")

    logs = log_path.read_text(encoding="utf-8")
    assert result == "ok"
    assert "event=tool.start" in logs
    assert "event=tool.finish" in logs
    assert "duration_ms=" in logs
    assert "hidden" not in logs
    assert "large input" not in logs


@pytest.mark.asyncio
async def test_tool_logging_records_safe_argument_summary(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "tools.log"
    settings = LoggingSettings(
        console_enabled=False,
        file_path=log_path,
        tool_args_enabled=True,
        max_field_length=8,
    )
    configure_logging(settings)

    @log_mcp_tool("sample_tool", settings)
    async def sample_tool(secret_token: str, query: str, payload: dict[str, str]) -> str:
        return "ok"

    await sample_tool(
        secret_token="hidden",
        query="abcdefghijklmnopqrstuvwxyz",
        payload={"password": "hidden", "visible": "yes"},
    )

    logs = log_path.read_text(encoding="utf-8")
    assert "secret_token" in logs
    assert "<redacted>" in logs
    assert "abcde..." in logs
    assert "visible" in logs
    assert "hidden" not in logs


@pytest.mark.asyncio
async def test_tool_logging_records_error_and_reraises(tmp_path: Path) -> None:
    log_path = tmp_path / "tools.log"
    settings = LoggingSettings(console_enabled=False, file_path=log_path)
    configure_logging(settings)

    @log_mcp_tool("failing_tool", settings)
    async def failing_tool() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await failing_tool()

    logs = log_path.read_text(encoding="utf-8")
    assert "event=tool.error" in logs
    assert "error_type=RuntimeError" in logs
    assert "duration_ms=" in logs
