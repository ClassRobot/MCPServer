"""底层数据库持久化交互的规范化展示数据结构定义。

本包下的 Schema 用于将 SQLAlchemy ORM 模型安全映射并转换输出为符合 MCP 通信要求的协议对象。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QueryRecord:
    """持久化的单条搜索历史记录的规范化输出数据类。"""

    id: str
    query: str
    provider: str
    source_tool: str
    notes: str | None
    created_at: str


@dataclass(slots=True)
class TaskExecutionRecord:
    """任务执行流水历史行记录的只读结构体（主要为后续运行时任务编排保留）。"""

    id: str
    task_name: str
    status: str
    details_json: str | None
    created_at: str


@dataclass(slots=True)
class PersistedConfigItem:
    """在共享关系型数据库中持久化存储的运行时动态配置项。"""

    key: str
    value_json: str
    description: str | None
    created_at: str
    updated_at: str
