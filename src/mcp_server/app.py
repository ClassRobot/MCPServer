"""MCP 服务端应用程序的组装与生命周期管理中心。

负责实例化基础设施适配器、业务领域服务，完成 FastMCP 实例的构建，
并注册所有的工具 (Tools)、资源 (Resources) 及提示词 (Prompts)。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .adapters.baidu_provider import BaiduSearchProvider
from .adapters.bing_provider import BingSearchProvider
from .adapters.browser_session import BrowserSessionManager
from .adapters.database import DatabaseManager
from .adapters.search_cache import SearchCacheStore
from .config import ServerSettings, load_server_settings
from .prompts import register_prompts
from .resources import register_resources
from .services.browser_search import BrowserSearchService
from .services.office import OfficeDocumentService
from .services.pdf_reader import PDFReadingService
from .services.query_history import QueryHistoryService
from .services.rendering import ContentRenderingService
from .services.search_results import SearchResultFilter
from .tools import register_tools


def create_server(settings: ServerSettings | None = None) -> FastMCP:
    """创建并配置 FastMCP 应用服务器实例。

    负责装配底层的 Session/Cache/Database 适配器，初始化业务服务层，
    设置服务的异步生命周期管理（lifespan），并注册所有的 MCP 协议能力。

    Args:
        settings (ServerSettings | None): 全局服务器配置对象。若为 None 则默认从本地 YAML 或环境变量中加载。

    Returns:
        FastMCP: 配置齐全且已装配完毕的 FastMCP 实例。
    """
    active_settings = settings or load_server_settings()

    # 1. 初始化基础设施层适配器（管理无头浏览器会话、本地持久化缓存及持久化数据库）
    session_manager = BrowserSessionManager(active_settings.browser_search.browser)
    cache_store = SearchCacheStore(active_settings.browser_search.cache)
    database_manager = DatabaseManager(active_settings.database)

    # 2. 实例化各个核心业务领域的服务层（Domain Services）
    result_filter = SearchResultFilter(active_settings.browser_search.filter)
    browser_search_service = BrowserSearchService(
        session_manager=session_manager,
        cache_store=cache_store,
        providers={
            "bing": BingSearchProvider(active_settings.browser_search.browser),
            "baidu": BaiduSearchProvider(active_settings.browser_search.browser),
        },
        result_filter=result_filter,
        browser_settings=active_settings.browser_search.browser,
        cache_settings=active_settings.browser_search.cache,
    )
    rendering_service = ContentRenderingService(
        session_manager=session_manager,
        default_output_dir=active_settings.render_output_dir,
    )
    query_history_service = QueryHistoryService(database_manager)
    pdf_service = PDFReadingService(default_output_dir=active_settings.render_output_dir)
    office_service = OfficeDocumentService(
        default_output_dir=active_settings.render_output_dir,
        pdf_service=pdf_service,
    )

    # 3. 定义 FastMCP 异步上下文管理器，控制数据库连接的初始化与释放，以及浏览器会话的清理
    @asynccontextmanager
    async def lifespan(_: FastMCP):
        try:
            # 服务启动时初始化数据库模型与异步引擎
            await database_manager.initialize()
            yield
        finally:
            # 服务关闭时安全断开数据库池，并强力回收所有残留的浏览器会话
            await database_manager.dispose()
            await session_manager.close_all()

    # 4. 创建 FastMCP 服务器对象，传入服务参数
    mcp = FastMCP(
        name=active_settings.name,
        instructions=active_settings.instructions,
        host=active_settings.host,
        port=active_settings.port,
        mount_path=active_settings.mount_path,
        streamable_http_path=active_settings.streamable_http_path,
        stateless_http=active_settings.stateless_http,
        json_response=active_settings.json_response,
        lifespan=lifespan,
    )

    # 5. 注册所有的外部开放工具能力（如浏览器搜索、 office渲染、 pdf提取、ECharts图表绘制等）
    register_tools(
        mcp,
        settings=active_settings,
        browser_search_service=browser_search_service,
        session_manager=session_manager,
        query_history_service=query_history_service,
        rendering_service=rendering_service,
        pdf_service=pdf_service,
        office_service=office_service,
    )
    
    # 6. 注册所有的 MCP 协议静态与动态资源（提供严格网络资源模式文件读取）
    register_resources(
        mcp,
        query_history_service=query_history_service,
        render_output_dir=active_settings.render_output_dir,
    )
    
    # 7. 注册 AI 交互提示词模板（Prompts）
    register_prompts(mcp)
    
    return mcp
