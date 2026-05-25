"""Central logging setup for terminal and local file output."""

from __future__ import annotations

import json
import logging
import sys
from copy import deepcopy
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any

from mcp_server.config import LoggingSettings

_HANDLER_MARKER = "_mcp_server_handler"
_UVICORN_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")
_LIBRARY_LOGGER_PREFIXES = ("mcp",)
_RESET = "\033[0m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_BLUE = "\033[34m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD_RED = "\033[1;31m"
_LEVEL_COLORS = {
    "DEBUG": _BLUE,
    "INFO": _GREEN,
    "WARNING": _YELLOW,
    "ERROR": _RED,
    "CRITICAL": _BOLD_RED,
}


class KeyValueFormatter(logging.Formatter):
    """Format log records as human-readable messages with key=value context."""

    def __init__(self, *, use_colors: bool = False) -> None:
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%m-%d %H:%M:%S")
        level_name = f"[{record.levelname}]"
        level_color = _LEVEL_COLORS.get(record.levelname)

        short_name = record.name.split(".")[0]
        header_parts = [
            self._color(timestamp, level_color),
            self._color(level_name, level_color),
            self._color(short_name, _CYAN),
        ]
        header = " ".join(header_parts)

        body_parts = []
        event = getattr(record, "mcp_event", None)
        if event:
            body_parts.append(self._format_field("event", event, key_color=_BLUE))

        message = record.getMessage()
        if message:
            body_parts.append(message)

        fields = getattr(record, "mcp_fields", None)
        if isinstance(fields, dict):
            body_parts.extend(
                self._format_field(str(key), value)
                for key, value in fields.items()
                if value is not None
            )

        body = " ".join(body_parts)
        formatted = f"{header} | {body}" if body else header

        if record.exc_info:
            formatted = f"{formatted}\n{self.formatException(record.exc_info)}"
        return formatted

    def _format_field(self, key: str, value: Any, *, key_color: str = _DIM) -> str:
        return f"{self._color(key, key_color)}={_format_value(value)}"

    def _color(self, text: str, color_code: str | None) -> str:
        if not self.use_colors or color_code is None:
            return text
        return f"{color_code}{text}{_RESET}"


def configure_logging(settings: LoggingSettings) -> None:
    """Configure project logging handlers in an idempotent way."""
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        if getattr(handler, _HANDLER_MARKER, False):
            handler.close()

    console_formatter = KeyValueFormatter(use_colors=settings.console_color_enabled)
    file_formatter = KeyValueFormatter(use_colors=False)

    if settings.console_enabled:
        console_handler = logging.StreamHandler(sys.stderr)
        _configure_handler(console_handler, console_formatter, settings.level)
        root_logger.addHandler(console_handler)

    if settings.file_enabled:
        settings.file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=settings.file_path,
            when="midnight",
            interval=1,
            backupCount=settings.retention_days,
            encoding="utf-8",
        )
        _configure_handler(file_handler, file_formatter, settings.level)
        root_logger.addHandler(file_handler)

    configure_library_loggers(settings)
    configure_uvicorn_logging(settings)


def configure_library_loggers(settings: LoggingSettings) -> None:
    """Route known library loggers through the project root handlers."""
    logger_names = {
        name
        for name in logging.Logger.manager.loggerDict
        if any(
            name == prefix or name.startswith(f"{prefix}.") for prefix in _LIBRARY_LOGGER_PREFIXES
        )
    }
    logger_names.update(_LIBRARY_LOGGER_PREFIXES)

    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        logger.disabled = False
        logger.setLevel(settings.level)
        logger.propagate = True
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            if getattr(handler, _HANDLER_MARKER, False):
                handler.close()


def configure_uvicorn_logging(settings: LoggingSettings) -> None:
    """Make Uvicorn use the same terminal and file log format as the app.

    To prevent duplicate file handlers opening the same file (which crashes on
    daily rotation on Windows), we route Uvicorn loggers to propagate to the
    root logger instead of having their own handlers.
    """
    try:
        import uvicorn.config
    except ImportError:
        return

    uvicorn_log_config = deepcopy(uvicorn.config.LOGGING_CONFIG)
    uvicorn_log_config["formatters"] = {
        "console": {
            "()": "mcp_server.logging_config.KeyValueFormatter",
            "use_colors": settings.console_color_enabled,
        },
    }
    uvicorn_log_config["handlers"] = {}
    uvicorn_log_config["loggers"] = {
        logger_name: {
            "handlers": [],
            "level": settings.level,
            "propagate": True,
        }
        for logger_name in _UVICORN_LOGGER_NAMES
    }

    uvicorn.config.LOGGING_CONFIG.clear()
    uvicorn.config.LOGGING_CONFIG.update(uvicorn_log_config)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured project event with key=value context."""
    exc_info = fields.pop("exc_info", None)
    logger.log(
        level,
        "",
        extra={"mcp_event": event, "mcp_fields": fields},
        exc_info=exc_info,
    )


def _configure_handler(
    handler: logging.Handler,
    formatter: logging.Formatter,
    level: str,
) -> None:
    """Apply common handler settings and mark project-owned handlers."""
    handler.setLevel(level)
    handler.setFormatter(formatter)
    setattr(handler, _HANDLER_MARKER, True)


def _format_value(value: Any) -> str:
    """Format a value for logfmt-style output."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | float):
        return str(value)
    if value is None:
        return "null"

    text = str(value)
    if text == "" or any(character.isspace() for character in text):
        return json.dumps(text, ensure_ascii=False)
    return text
