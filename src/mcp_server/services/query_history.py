"""搜索查询历史记录持久化操作的业务服务层。

该模块对外提供高层次的查询历史记录写入与读取的业务封装，
内部调度关系型数据库管理器、持久化实体模型以及底层仓储层(Repository)实现。
"""

from __future__ import annotations

from mcp_server.adapters.database import DatabaseManager
from mcp_server.adapters.database_models import QueryRecordModel
from mcp_server.adapters.query_history_repository import QueryHistoryRepository
from mcp_server.schemas.database import QueryRecord


class QueryHistoryService:
    """查询历史记录服务类。

    封装了与关系型数据库底座的会话流转，提供向数据库记录单条搜索历史及检索近期查询列表的核心业务接口。
    """

    def __init__(self, database_manager: DatabaseManager) -> None:
        """初始化查询历史记录服务。

        Args:
            database_manager (DatabaseManager): 用于分配并管理 SQLAlchemy 异步 Session 的数据库管理器。
        """
        self._database_manager = database_manager

    async def record_query(
        self,
        *,
        query: str,
        provider: str,
        source_tool: str,
        notes: str | None = None,
    ) -> QueryRecord:
        """规范化并安全持久化单条搜索查询历史行记录，并返回结构化的视图模式数据。

        Args:
            query (str): 被检索的原始用户提示词短语。
            provider (str): 使用的搜索引擎服务商标识，例如 "bing" 或 "baidu"。
            source_tool (str): 触发本条历史写入的工具来源（例如 "web_search"）。
            notes (str | None): 可选的补充元数据或上下文关联备注。

        Returns:
            QueryRecord: 写入成功后转换生成的只读结构化 schema 实体。

        Raises:
            ValueError: 任何必填字段经过清洗后变为空白字符串。
        """
        # 1. 规整输入字段，折叠多余空白符以防噪声数据入库
        normalized_query = self._normalize_non_empty(query, field_name="query")
        normalized_provider = self._normalize_non_empty(provider, field_name="provider")
        normalized_source_tool = self._normalize_non_empty(
            source_tool,
            field_name="source_tool",
        )
        normalized_notes = notes.strip() if notes is not None else None

        # 2. 通过异步 Session 块安全流转数据库连接
        async with self._database_manager.session() as session:
            repository = QueryHistoryRepository(session)
            # 调用仓储层在 Session 缓冲区内构建实体模型
            record = await repository.create(
                query=normalized_query,
                provider=normalized_provider,
                source_tool=normalized_source_tool,
                notes=normalized_notes or None,
            )
            # 显式提交事务，把脏数据刷入物理磁盘
            await session.commit()
            return self._to_schema(record)

    async def list_recent_queries(self, *, limit: int = 10) -> list[QueryRecord]:
        """获取最近一段时间持久化的历史查询记录列表（按创建时间降序）。

        Args:
            limit (int): 返回结果的最大记录条数限制，默认值为 10。

        Returns:
            list[QueryRecord]: 包含结构化历史记录对象的列表。

        Raises:
            ValueError: limit 传入了非正整数。
        """
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")

        # 使用异步 Session 管理数据库只读会话
        async with self._database_manager.session() as session:
            repository = QueryHistoryRepository(session)
            # 从仓储层中分页拉取最新记录集合
            records = await repository.list_recent(limit=limit)
            # 批量将 ORM 模型映射为面向展示的规范化 Schema 对象
            return [self._to_schema(record) for record in records]

    def _normalize_non_empty(self, value: str, *, field_name: str) -> str:
        """净化必须的非空字符串字段，折叠换行与连续空格，并对空值抛出异常。"""
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized

    def _to_schema(self, record: QueryRecordModel) -> QueryRecord:
        """将底层数据库的 SQLAlchemy ORM 对象高效映射为 MCP 传输安全的 Schema 结构体。"""
        return QueryRecord(
            id=record.id,
            query=record.query,
            provider=record.provider,
            source_tool=record.source_tool,
            notes=record.notes,
            # 将 datetime 时区对象转换为标准的符合 ISO-8601 约定的 UTC 字符串
            created_at=record.created_at.isoformat(),
        )
