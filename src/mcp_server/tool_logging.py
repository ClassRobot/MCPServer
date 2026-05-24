"""MCP tool call logging helpers."""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, get_type_hints
from uuid import uuid4

from mcp_server.config import LoggingSettings
from mcp_server.logging_config import log_event

F = TypeVar("F", bound=Callable[..., Any])

SENSITIVE_FIELD_NAMES = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "state",
    "token",
}


def log_mcp_tool(tool_name: str, settings: LoggingSettings) -> Callable[[F], F]:
    """Wrap an MCP tool function with start, finish, and error logs."""

    def decorator(func: F) -> F:
        annotations = _resolve_annotations(func)
        signature = _resolve_signature(inspect.signature(func), annotations)
        logger = logging.getLogger(f"mcp_server.tools.{tool_name}")

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                call_id = uuid4().hex[:8]
                started_at = time.perf_counter()
                _log_tool_start(
                    logger,
                    tool_name,
                    call_id,
                    signature,
                    settings,
                    args,
                    kwargs,
                )
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    _log_tool_error(logger, tool_name, call_id, started_at, exc)
                    raise
                _log_tool_finish(logger, tool_name, call_id, started_at)
                return result

            _copy_function_metadata(async_wrapper, signature, annotations)
            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            call_id = uuid4().hex[:8]
            started_at = time.perf_counter()
            _log_tool_start(
                logger,
                tool_name,
                call_id,
                signature,
                settings,
                args,
                kwargs,
            )
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                _log_tool_error(logger, tool_name, call_id, started_at, exc)
                raise
            _log_tool_finish(logger, tool_name, call_id, started_at)
            return result

        _copy_function_metadata(sync_wrapper, signature, annotations)
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _resolve_annotations(func: Callable[..., Any]) -> dict[str, Any]:
    """Resolve postponed annotations before FastMCP builds Pydantic schemas."""
    try:
        return get_type_hints(func)
    except Exception:
        return dict(getattr(func, "__annotations__", {}))


def _resolve_signature(
    signature: inspect.Signature,
    annotations: dict[str, Any],
) -> inspect.Signature:
    """Return a signature whose annotations are real objects, not strings."""
    parameters = [
        parameter.replace(annotation=annotations.get(name, parameter.annotation))
        for name, parameter in signature.parameters.items()
    ]
    return signature.replace(
        parameters=parameters,
        return_annotation=annotations.get("return", signature.return_annotation),
    )


def _copy_function_metadata(
    wrapper: Callable[..., Any],
    signature: inspect.Signature,
    annotations: dict[str, Any],
) -> None:
    """Expose the original callable contract on the logging wrapper."""
    wrapper.__signature__ = signature  # type: ignore[attr-defined]
    wrapper.__annotations__ = annotations


def _log_tool_start(
    logger: logging.Logger,
    tool_name: str,
    call_id: str,
    signature: inspect.Signature,
    settings: LoggingSettings,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    """Log the beginning of a tool call with optional safe argument summaries."""
    fields: dict[str, Any] = {"tool": tool_name, "call_id": call_id}
    if settings.tool_args_enabled:
        fields["args"] = _summarize_arguments(signature, args, kwargs, settings)
    log_event(logger, logging.INFO, "tool.start", **fields)


def _log_tool_finish(
    logger: logging.Logger,
    tool_name: str,
    call_id: str,
    started_at: float,
) -> None:
    """Log successful completion of a tool call."""
    log_event(
        logger,
        logging.INFO,
        "tool.finish",
        tool=tool_name,
        call_id=call_id,
        duration_ms=_elapsed_ms(started_at),
    )


def _log_tool_error(
    logger: logging.Logger,
    tool_name: str,
    call_id: str,
    started_at: float,
    exc: Exception,
) -> None:
    """Log a failed tool call while preserving the original exception."""
    log_event(
        logger,
        logging.ERROR,
        "tool.error",
        tool=tool_name,
        call_id=call_id,
        duration_ms=_elapsed_ms(started_at),
        error_type=type(exc).__name__,
        error_message=str(exc),
        exc_info=True,
    )


def _elapsed_ms(started_at: float) -> int:
    """Return elapsed wall-clock time in milliseconds."""
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _summarize_arguments(
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    settings: LoggingSettings,
) -> dict[str, Any]:
    """Return a safe, compact summary of tool arguments."""
    bound = signature.bind_partial(*args, **kwargs)
    return {
        name: _summarize_value(name, value, settings.max_field_length)
        for name, value in bound.arguments.items()
    }


def _summarize_value(name: str, value: Any, max_length: int) -> Any:
    """Summarize values without leaking large payloads or sensitive fields."""
    if _is_sensitive_name(name):
        return "<redacted>"
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _truncate(value, max_length)
    if isinstance(value, bytes | bytearray):
        return f"<{type(value).__name__} length={len(value)}>"
    if isinstance(value, Path):
        return _truncate(str(value), max_length)
    if isinstance(value, dict):
        visible_keys = [
            "<redacted>" if _is_sensitive_name(str(key)) else str(key)
            for key in list(value.keys())[:10]
        ]
        return {"type": "dict", "size": len(value), "keys": visible_keys}
    if isinstance(value, list | tuple | set | frozenset):
        return {"type": type(value).__name__, "size": len(value)}
    return _truncate(f"<{type(value).__name__}>", max_length)


def _is_sensitive_name(name: str) -> bool:
    """Return whether a field name should be redacted in logs."""
    normalized = name.lower()
    return any(fragment in normalized for fragment in SENSITIVE_FIELD_NAMES)


def _truncate(value: str, max_length: int) -> str:
    """Trim long log values while preserving their beginning."""
    if len(value) <= max_length:
        return value
    return f"{value[: max(0, max_length - 3)]}..."
