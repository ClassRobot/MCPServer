"""高阶网页搜索服务的调度器与编排层。

负责对输入查询词实施清洗，根据选择的引擎路由到特定的适配器，
通过有状态浏览器会话管理器拉起无头沙箱，并组合执行缓存读写、广告过滤及快照摘要。
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.adapters.search_cache import SearchCacheStore
from mcp_server.config import BrowserSettings, SearchCacheSettings
from mcp_server.schemas import BrowserSearchResponse, RawSearchResult, SearchResult
from mcp_server.services.search_results import SearchResultFilter


class BrowserSearchProvider(Protocol):
    """底层搜索引擎适配器的 Protocol 协议约定。"""

    async def search(
        self,
        session_manager: BrowserSessionManager,
        session_id: str,
        query: str,
    ) -> list[RawSearchResult]:
        """执行具体搜索引擎页面检索并返回原始候选结果包。"""


class BrowserSearchService:
    """高层网页搜索调度服务。

    编排并整合搜索引擎调用、广告拦截器校验、LRU缓存管理及结果序列化排序。
    """

    def __init__(self, *,
        session_manager: BrowserSessionManager,
        cache_store: SearchCacheStore,
        providers: dict[str, BrowserSearchProvider],
        result_filter: SearchResultFilter,
        browser_settings: BrowserSettings,
        cache_settings: SearchCacheSettings,
    ) -> None:
        """初始化浏览器搜索服务。

        Args:
            session_manager (BrowserSessionManager): 浏览器有状态会话管理器。
            cache_store (SearchCacheStore): 搜索结果的磁盘缓存器。
            providers (dict[str, BrowserSearchProvider]): 已注册的搜索引擎提供商映射字典。
            result_filter (SearchResultFilter): 结果过滤器组件。
            browser_settings (BrowserSettings): 浏览器运行环境设置。
            cache_settings (SearchCacheSettings): 缓存失效策略设置。
        """
        self._session_manager = session_manager
        self._cache_store = cache_store
        self._providers = providers
        self._result_filter = result_filter
        self._browser_settings = browser_settings
        self._cache_settings = cache_settings

    async def search(self, *,
        query: str,
        provider: str = "bing",
        max_results: int | None = None,
        include_summary: bool = False,
        use_cache: bool = True,
        force_refresh: bool = False,
        filter_ads: bool = True,
    ) -> BrowserSearchResponse:
        """执行端到端有缓存保证的高层网页检索。

        Args:
            query (str): 待检索的原始用户提示词或短语。
            provider (str): 目标搜索引擎类型，支持 "bing" 或 "baidu"。
            max_results (int | None): 返回的最高自然项数量。
            include_summary (bool): 是否随同返回首屏三条结果生成的简易文本摘要。
            use_cache (bool): 是否尝试读取本地持久化磁盘缓存。
            force_refresh (bool): 是否强制穿透缓存直达源站刷新。
            filter_ads (bool): 是否应用广告拦截清洗规则。

        Returns:
            BrowserSearchResponse: 规范化结果包。
        """
        # 1. 规整化查询字符串，去除多余空白符防噪
        normalized_query = self._normalize_query(query)
        resolved_provider = provider or self._browser_settings.default_provider
        provider_impl = self._providers.get(resolved_provider)
        if provider_impl is None:
            raise RuntimeError(f"Unsupported search provider: {resolved_provider!r}.")

        limit = max_results or self._browser_settings.max_results
        if limit <= 0:
            raise ValueError("max_results must be a positive integer.")

        # 2. 构建确定性散列 Key
        cache_key = self._cache_store.build_cache_key(
            provider=resolved_provider,
            normalized_query=normalized_query,
            max_results=limit,
            filter_ads=filter_ads,
            include_summary=include_summary,
        )

        # 3. 拦截缓存逻辑
        if use_cache and self._cache_settings.enabled and not force_refresh:
            cached_response = self._cache_store.get(cache_key)
            if cached_response is not None:
                return cached_response

        # 4. 创建无头沙箱浏览器页面，并在 finally 中确保销毁释放，防句柄泄露
        session_info = await self._session_manager.create_session()
        try:
            raw_results = await provider_impl.search(
                self._session_manager,
                session_info.session_id,
                normalized_query,
            )
        finally:
            await self._session_manager.close_session(session_info.session_id)

        # 5. 清除商业广告推广，截断指定条数，并自适应排序重设 Rank 索引
        filtered_results, filtered_count = self._result_filter.filter_results(
            raw_results,
            filter_ads=filter_ads,
        )
        limited_results = self._apply_limit(filtered_results, limit)
        summary = self._build_summary(limited_results) if include_summary else None

        response = BrowserSearchResponse(
            query=normalized_query,
            provider=resolved_provider,
            results=limited_results,
            summary=summary,
            cache_hit=False,
            filtered_count=filtered_count,
        )

        # 6. 后台执行文件持久化
        if use_cache and self._cache_settings.enabled:
            # 写入物理磁盘是同步阻塞 I/O，使用 to_thread 托管至底层线程池执行，防挂起 asyncio 主事件循环
            await asyncio.to_thread(self._cache_store.set, cache_key, response)
            
        return response

    def _normalize_query(self, query: str) -> str:
        """净化搜索词，折叠连续的空格。"""
        normalized = " ".join(query.split()).strip()
        if not normalized:
            raise ValueError("query must not be empty.")
        return normalized

    def _apply_limit(self, results: list[SearchResult], limit: int) -> list[SearchResult]:
        """安全截断结果数，并从 1 开始重新分配排位名次（Rank）。"""
        limited = results[:limit]
        for index, result in enumerate(limited, start=1):
            result.rank = index
        return limited

    def _build_summary(self, results: list[SearchResult]) -> str | None:
        """根据排名最高的前三条自然网页结果，智能组装简易文本摘要。"""
        if not results:
            return None

        summary_lines = []
        for result in results[:3]:
            if result.snippet:
                summary_lines.append(f"{result.rank}. {result.title}: {result.snippet}")
            else:
                summary_lines.append(f"{result.rank}. {result.title}")
        return "Top search results:\n" + "\n".join(summary_lines)
