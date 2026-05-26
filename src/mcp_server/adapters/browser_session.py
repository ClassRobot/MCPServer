"""基于 Playwright 驱动的有状态浏览器会话生命周期与控制管理器。

提供多会话并发管理能力，支持会话定时过期清理、延迟懒加载初始化、
Cookie 登录态存盘与加载，以及低阶的网页输入、点击、内容提取等 RPA 自动化操作。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin
from uuid import uuid4

from bs4 import BeautifulSoup
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from mcp_server.config import BrowserSettings
from mcp_server.schemas import (
    BrowserExtractLink,
    BrowserExtractResult,
    BrowserSessionInfo,
)


@dataclass(slots=True)
class ManagedBrowserSession:
    """运行时单浏览器会话的状态容器类。"""

    session_id: str
    browser: Browser
    context: BrowserContext
    page: Page
    headless: bool
    created_at: datetime
    last_used_at: datetime


class BrowserSessionManager:
    """有状态浏览器会话管理器。

    提供低阶 RPA 工具和高层网页搜索引擎共用的浏览器上下文调度，支持线程安全的惰性加载。
    """

    def __init__(self, settings: BrowserSettings) -> None:
        """初始化会话管理器。

        Args:
            settings (BrowserSettings): 浏览器运行配置。
        """
        self._settings = settings
        self._playwright: Playwright | None = None
        self._sessions: dict[str, ManagedBrowserSession] = {}
        self._lock = asyncio.Lock()  # 协程异步锁，确保多线程/协程并发加载 Playwright 时是线程安全的

    async def create_session(
        self,
        headless: bool | None = None,
        storage_state_path: str | None = None,
    ) -> BrowserSessionInfo:
        """创建一个全新的独立浏览器会话，并返回其公开元数据。

        Args:
            headless (bool | None): 是否使用无头模式。若为 None 则默认使用全局配置。
            storage_state_path (str | None): 导出的 Cookies 或 LocalStorage JSON 状态路径。

        Returns:
            BrowserSessionInfo: 新会话的描述元数据（session_id, headless）。
        """
        # 1. 触发过期会话的清理回收
        await self._cleanup_expired_sessions()
        playwright = await self._ensure_playwright()
        
        session_headless = self._settings.headless if headless is None else headless
        
        # 2. 启动 Chromium 物理子进程
        browser = await playwright.chromium.launch(headless=session_headless)
        try:
            context_kwargs: dict[str, Any] = {}
            if self._settings.user_agent is not None:
                context_kwargs["user_agent"] = self._settings.user_agent
            if storage_state_path is not None:
                # 如果传入了状态文件路径，直接在此注入 Cookie/LocalStorage 恢复登录态
                context_kwargs["storage_state"] = storage_state_path
                
            context = await browser.new_context(**context_kwargs)
            try:
                page = await context.new_page()
            except Exception:
                await context.close()
                raise
        except Exception:
            await browser.close()
            raise

        session_id = uuid4().hex
        timestamp = datetime.now(UTC)
        
        # 3. 计入活跃会话表
        self._sessions[session_id] = ManagedBrowserSession(
            session_id=session_id,
            browser=browser,
            context=context,
            page=page,
            headless=session_headless,
            created_at=timestamp,
            last_used_at=timestamp,
        )
        return BrowserSessionInfo(session_id=session_id, headless=session_headless)

    async def open(self, session_id: str, url: str) -> dict[str, str]:
        """在指定的会话页面中导航加载目标网页。

        Args:
            session_id (str): 浏览器会话 ID。
            url (str): 目标加载 URL。

        Returns:
            dict[str, str]: 包含会话 ID、最终 URL 以及页面 Title 的键值对结果。
        """
        page = await self.get_page(session_id)
        try:
            await page.goto(url, wait_until="load", timeout=self._settings.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"导航加载目标网页 {url!r} 超时。") from exc
        except PlaywrightError as exc:
            raise RuntimeError(f"导航加载目标网页 {url!r} 失败：{exc}") from exc
        return {
            "session_id": session_id,
            "url": page.url,
            "title": await page.title(),
        }

    async def fill(
        self, session_id: str, selector: str, value: str, clear: bool = True
    ) -> dict[str, str]:
        """在指定页面会话的 DOM 节点输入框中填充内容。

        Args:
            session_id (str): 浏览器会话 ID。
            selector (str): 目标输入框的 CSS Selector。
            value (str): 需要填入的文本值。
            clear (bool): 是否在填入前清空已有字符。默认为 True。

        Returns:
            dict[str, str]: 执行完毕的填充描述信息。
        """
        page = await self.get_page(session_id)
        try:
            if clear:
                await page.fill(selector, "", timeout=self._settings.timeout_ms)
            await page.fill(selector, value, timeout=self._settings.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"在 CSS 选择器 {selector!r} 处执行输入时超时。") from exc
        except PlaywrightError as exc:
            raise RuntimeError(f"在 CSS 选择器 {selector!r} 处执行输入时失败：{exc}") from exc
        return {
            "session_id": session_id,
            "selector": selector,
            "value": value,
        }

    async def click(
        self,
        session_id: str,
        selector: str,
        wait_for_network_idle: bool = True,
    ) -> dict[str, str]:
        """在指定页面会话中点击指定的 DOM 元素。

        Args:
            session_id (str): 浏览器会话 ID。
            selector (str): 点击目标的 CSS Selector。
            wait_for_network_idle (bool): 是否点击后等待网络请求静默闲置（通常用于 AJAX 响应网页）。

        Returns:
            dict[str, str]: 点击操作后的页面状态信息。
        """
        page = await self.get_page(session_id)
        try:
            await page.click(selector, timeout=self._settings.timeout_ms)
            if wait_for_network_idle:
                # 点击后静默等待，直至 500ms 内无新的网络连接触发
                await page.wait_for_load_state("networkidle", timeout=self._settings.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"点击 CSS 选择器 {selector!r} 时超时。") from exc
        except PlaywrightError as exc:
            raise RuntimeError(f"点击 CSS 选择器 {selector!r} 时失败：{exc}") from exc
        return {
            "session_id": session_id,
            "url": page.url,
            "title": await page.title(),
        }

    async def extract(
        self,
        session_id: str,
        selector: str | None = None,
        include_links: bool = False,
        max_links: int = 10,
    ) -> BrowserExtractResult:
        """从当前会话的网页（或特定子节点）中提炼清洗纯文本正文与外部超链接。

        Args:
            session_id (str): 浏览器会话 ID。
            selector (str | None): 局部的提取 CSS 选择器。若为 None 则默认扫描全网页 HTML。
            include_links (bool): 是否抓取节点内包含的 `a[href]` 超链接列表。
            max_links (int): 单次返回的链接最大上限数量。

        Returns:
            BrowserExtractResult: 包含标题、网址、清洗后文本及超链接的结构化结果。
        """
        page = await self.get_page(session_id)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. 提炼出选定的局部 DOM 树，若未指定则作用于全页面
        scope = soup.select_one(selector) if selector else soup
        text = scope.get_text(" ", strip=True) if scope is not None else ""

        links: list[BrowserExtractLink] = []
        if include_links and scope is not None:
            for link in scope.select("a[href]")[:max_links]:
                href = link.get("href", "").strip()
                if not href:
                    continue
                # 调用 urljoin，自动将相对路径转换为基于当前页面基准的绝对网络 URL
                links.append(
                    BrowserExtractLink(
                        text=link.get_text(" ", strip=True),
                        url=urljoin(page.url, href),
                    )
                )

        return BrowserExtractResult(
            session_id=session_id,
            title=await page.title(),
            url=page.url,
            text=text,
            links=links,
        )

    async def get_page(self, session_id: str) -> Page:
        """根据会话 ID 获取对应的活跃 Playwright 页面句柄，并刷新其空闲存活时间戳。

        Args:
            session_id (str): 目标会话的唯一标识 ID。

        Returns:
            Page: 活跃的 Playwright 页面句柄对象。
        """
        await self._cleanup_expired_sessions()
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"浏览器会话 {session_id!r} 不存在或已被定时过期回收释放。")
        # 每次使用时更新其最后使用时间戳，以顺延 TTL 周期
        session.last_used_at = datetime.now(UTC)
        return session.page

    async def close_session(self, session_id: str) -> dict[str, bool | str]:
        """主动回收并销毁一个特定的浏览器会话。

        Args:
            session_id (str): 浏览器会话 ID。

        Returns:
            dict[str, bool | str]: 会话关闭的最终状态。
        """
        session = self._sessions.pop(session_id, None)
        if session is None:
            return {"session_id": session_id, "closed": False}

        await session.context.close()
        await session.browser.close()
        return {"session_id": session_id, "closed": True}

    async def save_storage_state(self, session_id: str, dest_path: str) -> None:
        """导出当前会话的 Cookie/LocalStorage 状态，保存到磁盘指定的 JSON 文件中。

        Args:
            session_id (str): 浏览器会话 ID。
            dest_path (str): 导出的物理文件目标路径。
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"浏览器会话 {session_id!r} 不存在或已失效。")
        await session.context.storage_state(path=dest_path)

    async def close_all(self) -> None:
        """全局资源回收，安全销毁所有的活动浏览器实例，并退出 Playwright 驱动进程。"""
        session_ids = list(self._sessions)
        for session_id in session_ids:
            try:
                await self.close_session(session_id)
            except Exception:
                pass

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            finally:
                self._playwright = None

    async def _ensure_playwright(self) -> Playwright:
        """协程/线程安全的延迟懒加载初始化 Playwright。

        【特殊逻辑说明 - 并发锁保护】：
        多个并发请求同时到达时，为了防止在 _playwright 为空时重复并发开启多个 Playwright
        驱动主进程，在此使用 asyncio.Lock() 进行阻塞守护，确保整个服务生命周期内
        仅会懒加载实例化单个唯一的 playwright 服务流。
        """
        async with self._lock:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            return self._playwright

    async def _cleanup_expired_sessions(self) -> None:
        """协程独占锁下，定时扫表清除超过闲置存活期（TTL）的有状态浏览器会话。

        【TTL 算法说明】：
        - 获取当前 UTC 时间戳并倒推 `session_ttl_sec` 秒得到过期线时间（expiration_cutoff）。
        - 筛查所有 `last_used_at` 早于过期线的活动会话，并将它们逐一执行进程级 close 销毁，
          防止长时间闲置的无头浏览器进程发生句柄泄露、拖垮物理服务器内存。
        """
        async with self._lock:
            session_ttl = self._settings.session_ttl_sec
            expiration_cutoff = datetime.now(UTC) - timedelta(seconds=session_ttl)
            expired_ids = [
                session_id
                for session_id, session in self._sessions.items()
                if session.last_used_at < expiration_cutoff
            ]
            for session_id in expired_ids:
                await self.close_session(session_id)
