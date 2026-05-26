"""MCP 工具(Tools)的全局注册入口。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import ServerSettings
from mcp_server.services.browser_search import BrowserSearchService
from mcp_server.services.office import OfficeDocumentService
from mcp_server.services.pdf_reader import PDFReadingService
from mcp_server.services.query_history import QueryHistoryService
from mcp_server.services.rendering import ContentRenderingService

from .browser import register_browser_tools
from .database import register_database_tools
from .health import register_health_tools
from .office_tools import register_office_tools
from .pdf import register_pdf_tools
from .rendering import register_rendering_tools


def register_tools(
    mcp: FastMCP,
    *,
    settings: ServerSettings,
    browser_search_service: BrowserSearchService,
    session_manager: BrowserSessionManager,
    query_history_service: QueryHistoryService,
    rendering_service: ContentRenderingService,
    pdf_service: PDFReadingService,
    office_service: OfficeDocumentService,
) -> None:
    """向给定的 FastMCP 实例注册本项目暴露的所有 MCP 工具。

    Args:
        mcp (FastMCP): FastMCP 服务应用程序实例。
        settings (ServerSettings): 服务端全局核心配置对象。
        browser_search_service (BrowserSearchService): 网页多引擎高级搜索调度服务。
        session_manager (BrowserSessionManager): 有状态浏览器会话生命周期管理器。
        query_history_service (QueryHistoryService): 检索查询历史记录持久化服务。
        rendering_service (ContentRenderingService): Markdown/HTML 栅格化排版渲染及 ECharts 图表生成服务。
        pdf_service (PDFReadingService): PDF 文档高保真提取及渲染服务。
        office_service (OfficeDocumentService): Word/PPT 办公文档转换及渲染服务。
    """
    register_health_tools(mcp, logging_settings=settings.logging)
    register_database_tools(
        mcp,
        query_history_service=query_history_service,
        logging_settings=settings.logging,
    )
    register_browser_tools(
        mcp,
        settings=settings,
        browser_search_service=browser_search_service,
        session_manager=session_manager,
    )
    register_rendering_tools(
        mcp,
        rendering_service=rendering_service,
        logging_settings=settings.logging,
    )
    register_pdf_tools(
        mcp,
        pdf_service=pdf_service,
        project_root=settings.project_root,
        logging_settings=settings.logging,
    )
    register_office_tools(
        mcp,
        office_service=office_service,
        project_root=settings.project_root,
        logging_settings=settings.logging,
    )
