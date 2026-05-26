"""共享数据模式(Schemas)的接口导出包。

【可变性设计规范】
与配置模型(Config Models)不同，本包(schemas/)下的数据类 deliberately 未定义 `frozen=True`（仅声明 `slots=True`）。
这种设计旨在支持运行时的原地就地修改（例如：SearchResult 的动态排位顺序调整）。
除非能绝对确认后续业务无需任何状态变更，否则请勿将本包下的 Schema 数据类设为 `frozen=True`。
"""

from .browser import (
    BrowserExtractLink,
    BrowserExtractResult,
    BrowserSearchResponse,
    BrowserSessionInfo,
    RawSearchResult,
    SearchResult,
)
from .database import PersistedConfigItem, QueryRecord, TaskExecutionRecord
from .rendering import RenderImageResult

__all__ = [
    "BrowserExtractLink",
    "BrowserExtractResult",
    "BrowserSearchResponse",
    "BrowserSessionInfo",
    "PersistedConfigItem",
    "QueryRecord",
    "RawSearchResult",
    "SearchResult",
    "TaskExecutionRecord",
    "RenderImageResult",
]
