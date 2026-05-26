"""统一的日志系统配置模块，支持控制台终端高亮输出以及物理文件定时轮转。

支持键值对（logfmt）风格的日志结构化输出，并针对 Windows 平台下 Uvicorn
并发句柄锁定导致的日志文件滚动轮转 PermissionError [WinError 32] 异常进行了优化。
"""

from __future__ import annotations

import json
import logging
import sys
from copy import deepcopy
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any

from mcp_server.config import LoggingSettings

# 项目专有日志处理器的标识属性名，用于幂等清理
_HANDLER_MARKER = "_mcp_server_handler"
# 需要拦截并重定向其日志行为的 Uvicorn 相关记录器名称
_UVICORN_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")
# 项目专属库级别前缀
_LIBRARY_LOGGER_PREFIXES = ("mcp",)

# ANSI 控制台颜色转义字符常量定义
_RESET = "\033[0m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_BLUE = "\033[34m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD_RED = "\033[1;31m"

# 不同日志级别所映射的 ANSI 颜色通道
_LEVEL_COLORS = {
    "DEBUG": _BLUE,
    "INFO": _GREEN,
    "WARNING": _YELLOW,
    "ERROR": _RED,
    "CRITICAL": _BOLD_RED,
}


class KeyValueFormatter(logging.Formatter):
    """键值对结构化日志格式化器。

    将标准的 LogRecord 日志记录解析并拼接成人类易读且便于机器收集的
    `timestamp [LEVEL] module | event=name field1=val1 ...` 的 logfmt 风格字符串。
    """

    def __init__(self, *, use_colors: bool = False) -> None:
        """初始化格式化器。

        Args:
            use_colors (bool): 是否在输出中使用 ANSI 终端彩色转义字符。
        """
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """将日志记录对象格式化为 logfmt 风格行。

        Args:
            record (logging.LogRecord): 待格式化的日志实体。

        Returns:
            str: 格式化后的单行日志内容。
        """
        # 1. 组装标准的时间戳前缀
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

        # 2. 依次解析结构化字段（Event 事件名称、Message 纯文本以及自定义参数包）
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

        # 3. 如果携带异常堆栈追踪信息，则将其换行追加到日志末尾
        if record.exc_info:
            formatted = f"{formatted}\n{self.formatException(record.exc_info)}"
        return formatted

    def _format_field(self, key: str, value: Any, *, key_color: str = _DIM) -> str:
        """将一个特定的键值对字段转换为 key=value 形式，并在可能时给键上色。"""
        return f"{self._color(key, key_color)}={_format_value(value)}"

    def _color(self, text: str, color_code: str | None) -> str:
        """为文本包裹 ANSI 转义上色字符。"""
        if not self.use_colors or color_code is None:
            return text
        return f"{color_code}{text}{_RESET}"


def configure_logging(settings: LoggingSettings) -> None:
    """初始化并配置全局日志处理器，支持幂等重复调用。

    Args:
        settings (LoggingSettings): 全局日志参数模型。
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.level)

    # 1. 清理先前的日志处理器，以防重复注册导致输出重叠
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        if getattr(handler, _HANDLER_MARKER, False):
            handler.close()

    console_formatter = KeyValueFormatter(use_colors=settings.console_color_enabled)
    file_formatter = KeyValueFormatter(use_colors=False)

    # 2. 注册终端 stderr 标准输出流处理器
    if settings.console_enabled:
        console_handler = logging.StreamHandler(sys.stderr)
        _configure_handler(console_handler, console_formatter, settings.level)
        root_logger.addHandler(console_handler)

    # 3. 注册本地物理文件轮转处理器
    if settings.file_enabled:
        settings.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 每日午夜触发日志轮转，自动加上日期后缀归档，并清理过期的旧日志文件
        file_handler = TimedRotatingFileHandler(
            filename=settings.file_path,
            when="midnight",
            interval=1,
            backupCount=settings.retention_days,
            encoding="utf-8",
        )
        _configure_handler(file_handler, file_formatter, settings.level)
        root_logger.addHandler(file_handler)

    # 4. 配置子模块和第三方网络服务器日志重定向
    configure_library_loggers(settings)
    configure_uvicorn_logging(settings)


def configure_library_loggers(settings: LoggingSettings) -> None:
    """将已知库模块的日志重定向至当前根目录 Logger，统一输出格式。

    Args:
        settings (LoggingSettings): 日志配置。
    """
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
    """对 Uvicorn 日志架构实施拦截，使其套用本项目的键值对输出格式。

    【特殊逻辑说明 - 避免 Windows 权限锁死】：
    在 Windows 平台下，如果 Uvicorn 内部的 Logger 独立打开并持有了与本系统相同的物理
    日志文件句柄，在每日午夜日志滚动轮转（TimedRotatingFileHandler 进行 rename）时，
    操作系统会抛出 PermissionError [WinError 32] 导致崩溃。
    为了解决这一问题，我们将 Uvicorn 的所有处理器设为空，开启 `propagate=True` 允许它
    冒泡传递至根 Logger 统一输出，彻底消除句柄重复占用的问题。
    """
    try:
        import uvicorn.config
    except ImportError:
        return

    uvicorn_log_config = deepcopy(uvicorn.config.LOGGING_CONFIG)
    
    # 注入本项目的控制台键值格式化器
    uvicorn_log_config["formatters"] = {
        "console": {
            "()": "mcp_server.logging_config.KeyValueFormatter",
            "use_colors": settings.console_color_enabled,
        },
    }
    # 清除原处理器以实现事件冒泡
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
    """输出包含结构化参数包的 logfmt 事件记录。

    Args:
        logger (logging.Logger): 日志记录器。
        level (int): 日志级别（如 logging.INFO）。
        event (str): 结构化事件标识名（如 "database.query"）。
        **fields (Any): 伴随该事件的所有结构化键值参数载荷。
    """
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
    """应用处理器常规属性并为其打上项目所有的标记。"""
    handler.setLevel(level)
    handler.setFormatter(formatter)
    setattr(handler, _HANDLER_MARKER, True)


def _format_value(value: Any) -> str:
    """将一个值序列化为结构化 logfmt 兼容的输出格式。

    【格式化算法说明】：
    1. 布尔型转为 lower 格式（true/false）。
    2. 数值和 None 转换为标准化字面串。
    3. 如果值包含任何空白符（空格、换行、制表符等）或者是空串，
       则调用 json.dumps 包裹双引号并对特殊字符实施转义，确保机器完美按行分隔解析。
    """
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
