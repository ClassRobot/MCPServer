"""MCP 专用工具（Tools）调用拦截与结构化遥测日志辅助模块。

本模块提供了一个通用的修饰器装饰器，可在工具被调用时拦截入参和返回值，
自动打印开始、成功结束和异常失败日志。同时具备敏感参数脱敏与超长数据截断算法，
防止密钥和超大正文泄露至日志文件中。
"""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, get_type_hints
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from mcp_server.config import LoggingSettings
from mcp_server.logging_config import log_event

F = TypeVar("F", bound=Callable[..., Any])

# 定义敏感词汇，命中这些词汇的入参字段将被自动脱敏（Redacted）
SENSITIVE_FIELD_NAMES = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "state",
    "token",
}


def log_mcp_tool(tool_name: str, settings: LoggingSettings) -> Callable[[F], F]:
    """为 MCP 工具函数注入调用追踪和性能遥测日志的装饰器。

    支持对同步（sync）和异步（async）工具函数进行无感代理拦截。

    Args:
        tool_name (str): MCP 工具注册的名称。
        settings (LoggingSettings): 本地日志相关的环境参数配置。

    Returns:
        Callable[[F], F]: 代理函数包装器。
    """

    def decorator(func: F) -> F:
        # 1. 预先解析可能的字符串化延迟类型标注，保证 Pydantic 和 FastMCP 模式编译正常
        annotations = _resolve_annotations(func)
        signature = _resolve_signature(inspect.signature(func), annotations)
        logger = logging.getLogger(f"mcp_server.tools.{tool_name}")

        # 2. 如果是协程异步工具，返回异步异步拦截包装器
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                call_id = uuid4().hex[:8]  # 生成本次调用的局部随机 8 位唯一呼叫标识 ID
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

            # 将被拦截函数的反射签名复制给包装器，否则 FastMCP 将无法正确识别工具入参
            _copy_function_metadata(async_wrapper, signature, annotations)
            return async_wrapper  # type: ignore[return-value]

        # 3. 如果是常规同步工具，返回同步拦截包装器
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
    """在 Pydantic 进行 Schema 格式推演之前，强力解析任何延迟生成的类型标注（annotations）。

    【类型推导算法说明】：
    如果启用了 `from __future__ import annotations`，
    运行时的类型提示可能会被解析为纯字符串（例如 '"BrowserSettings"' 变为 str 类型）。
    通过 `get_type_hints` 可以自适应在当前的全局及局部作用域中将其反序列化为真正的 Python 类，
    以便 FastMCP 框架能正确输出对应接口入参的 OpenAPI JSON。
    """
    try:
        return get_type_hints(func)
    except Exception:
        return dict(getattr(func, "__annotations__", {}))


def _resolve_signature(
    signature: inspect.Signature,
    annotations: dict[str, Any],
) -> inspect.Signature:
    """用真实的 Python 类型实例替换签名中残留的纯文本字符串类型标注。"""
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
    """将原函数的调用契约拷贝到包装器，保证 FastMCP 反射正常读取。"""
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
    """输出工具开始被调用日志，自适应向日志中注入脱敏脱毒后的参数包摘要。"""
    fields: dict[str, Any] = {"tool": tool_name, "call_id": call_id}
    if settings.tool_args_enabled:
        # 当且仅当日志配置显式开启 tool_args 时，才对参数进行提纯脱敏后打印
        fields["args"] = _summarize_arguments(signature, args, kwargs, settings)
    log_event(logger, logging.INFO, "tool.start", **fields)

    # 尝试把当前进度上报给客户端侧（如 Claude Desktop 显示小进度条）
    try:
        ctx = FastMCP.get_context()
        if ctx:
            ctx.info(f"开始执行工具 {tool_name} (id: {call_id})")
    except Exception:
        pass


def _log_tool_finish(
    logger: logging.Logger,
    tool_name: str,
    call_id: str,
    started_at: float,
) -> None:
    """输出工具完美执行完毕日志，附带本次调用的精确耗时（毫秒）。"""
    duration = _elapsed_ms(started_at)
    log_event(
        logger,
        logging.INFO,
        "tool.finish",
        tool=tool_name,
        call_id=call_id,
        duration_ms=duration,
    )

    try:
        ctx = FastMCP.get_context()
        if ctx:
            ctx.info(f"工具 {tool_name} 执行完毕，耗时 {duration}ms")
    except Exception:
        pass


def _log_tool_error(
    logger: logging.Logger,
    tool_name: str,
    call_id: str,
    started_at: float,
    exc: Exception,
) -> None:
    """输出工具执行出错日志，同时完整打印对应的异常回溯栈。"""
    duration = _elapsed_ms(started_at)
    log_event(
        logger,
        logging.ERROR,
        "tool.error",
        tool=tool_name,
        call_id=call_id,
        duration_ms=duration,
        error_type=type(exc).__name__,
        error_message=str(exc),
        exc_info=True,
    )

    try:
        ctx = FastMCP.get_context()
        if ctx:
            ctx.error(f"工具 {tool_name} 执行失败：{exc}")
    except Exception:
        pass


def _elapsed_ms(started_at: float) -> int:
    """返回程序执行时消耗的墙上挂钟真实时间（毫秒）。"""
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _summarize_arguments(
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    settings: LoggingSettings,
) -> dict[str, Any]:
    """通过反射绑定位置参数与关键字参数，并对各参数进行结构化摘要清洗。"""
    bound = signature.bind_partial(*args, **kwargs)
    return {
        name: _summarize_value(name, value, settings.max_field_length)
        for name, value in bound.arguments.items()
    }


def _summarize_value(name: str, value: Any, max_length: int) -> Any:
    """实施字段脱敏与长正文裁剪。

    【核心脱敏过滤算法】：
    1. 字段名包含敏感片段（如 Token、Password、Authorization 等），直接红牌脱敏为 `<redacted>`。
    2. 数值或布尔等标量，保留原值输出。
    3. 超长字符串正文，调用首端自动截断（保留前缀，追加省略号）。
    4. 对二进制大字节数组（bytes）、大字典（dict）和大列表进行长度及大小摘要输出，避免巨大的 Base64 数据洪流压垮日志磁盘。
    """
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
    """返回传入的参数字段名是否命中敏感参数特征词汇，不区分大小写。"""
    normalized = name.lower()
    return any(fragment in normalized for fragment in SENSITIVE_FIELD_NAMES)


def _truncate(value: str, max_length: int) -> str:
    """当字符串超过配置长度时对其实施安全裁剪，并以 ... 填充后缀。"""
    if len(value) <= max_length:
        return value
    return f"{value[: max(0, max_length - 3)]}..."
