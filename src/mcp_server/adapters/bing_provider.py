"""Bing 搜索引擎页面解析与数据适配器。

驱动 Playwright 浏览器会话访问 Bing 搜索，等待核心节点渲染，
并通过 BeautifulSoup 提取、清洗网页结构中的自然搜索结果及广告推广链接。
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import BrowserSettings
from mcp_server.schemas import RawSearchResult


class BingSearchProvider:
    """Bing 搜索适配器类。

    构建 Bing 搜索 URL，并在已存在的浏览器页面会话中执行导航与内容提取。
    """

    def __init__(self, settings: BrowserSettings) -> None:
        """初始化 Bing 搜索适配器。

        Args:
            settings (BrowserSettings): 浏览器通用运行配置。
        """
        self._settings = settings

    def build_search_url(self, query: str) -> str:
        """构建 Bing 网页搜索的请求 URL。

        Args:
            query (str): 搜索关键词。

        Returns:
            str: 编码后的 Bing 搜索完整 URL。
        """
        return f"https://www.bing.com/search?q={quote_plus(query)}"

    async def search(
        self,
        session_manager: BrowserSessionManager,
        session_id: str,
        query: str,
    ) -> list[RawSearchResult]:
        """在指定的浏览器会话中执行 Bing 搜索并返回解析结果。

        Args:
            session_manager (BrowserSessionManager): 浏览器会话管理器。
            session_id (str): 目标会话的唯一标识 ID。
            query (str): 搜索关键词。

        Returns:
            list[RawSearchResult]: 结构化候选搜索结果列表。
        """
        page = await session_manager.get_page(session_id)
        await page.goto(
            self.build_search_url(query),
            wait_until="domcontentloaded",
            timeout=self._settings.timeout_ms,
        )
        try:
            # 等待 Bing 结果主节点 (#b_results) 附加到 DOM 中
            await page.wait_for_selector(
                "#b_results",
                state="attached",
                timeout=self._settings.timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Bing 搜索结果主容器 '#b_results' 未在超时限制内渲染完成。") from exc
        html = await page.content()
        return self.parse_results(html)

    def parse_results(self, html: str) -> list[RawSearchResult]:
        """使用 BeautifulSoup 对 Bing 搜索结果 HTML 进行清洗提纯。

        Args:
            html (str): Bing 搜索结果页面的完整 HTML 源码。

        Returns:
            list[RawSearchResult]: 解析出的搜索项（包含自然结果与广告标记）。
        """
        soup = BeautifulSoup(html, "html.parser")
        results_root = soup.select_one("#b_results")
        if results_root is None:
            return []

        parsed_results: list[RawSearchResult] = []
        for candidate in self._iter_candidates(results_root):
            classes = set(candidate.get("class", []))
            
            # 1. 提取标题和目标链接
            anchor = candidate.select_one("h2 a[href]") or candidate.select_one("a[href]")
            title = anchor.get_text(" ", strip=True) if anchor is not None else ""
            url = anchor.get("href", "").strip() if anchor is not None else ""
            
            # 2. 提取摘要段落
            snippet_node = candidate.select_one(".b_caption p") or candidate.select_one("p")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node is not None else None
            
            source = self._infer_source(url)
            
            # 3. 通过 Bing 专属样式类名确定自然结果并检查广告标签
            is_natural = "b_algo" in classes
            is_ad = self._looks_like_ad(candidate, classes)

            parsed_results.append(
                RawSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet or None,
                    source=source,
                    is_ad=is_ad,
                    is_natural=is_natural,
                )
            )
        return parsed_results

    def _iter_candidates(self, results_root: Tag) -> Iterable[Tag]:
        """迭代提取 Bing 主容器中的一级子卡片，自动跳过页码或旁支组件。

        【过滤算法说明】：
        - 排除分页栏（b_pag）及答主模块（b_ans）。
        - 保证子节点包含跳转链接（a[href]），否则无实际信息量。
        """
        for child in results_root.find_all(["li", "div"], recursive=False):
            if not isinstance(child, Tag):
                continue
            classes = set(child.get("class", []))
            if classes & {"b_pag", "b_ans"}:
                continue
            if child.select_one("a[href]") is None:
                continue
            yield child

    def _looks_like_ad(self, candidate: Tag, classes: set[str]) -> bool:
        """多重特征过滤算法判定是否为商业广告。

        【广告判定规则】：
        1. 检查节点自身的 class 样式中是否含有 ad、sponsored 等关键词。
        2. 扫描专有广告节点选择器（如 `.b_adLabel`, `[aria-label='Ad']` 等）。
        3. 合并提取特定角标文本，若含有 "ad"、"sponsored" 则认定为商业广告。
        """
        if classes & {"b_ad", "ads", "sponsored"}:
            return True

        marker_selectors = [
            ".b_adLabel",
            ".ads_label",
            ".sponsored",
            "[aria-label='Ad']",
        ]
        if any(candidate.select_one(selector) is not None for selector in marker_selectors):
            return True

        # 合并所有特征文本行进行词干分析
        marker_text = " ".join(
            marker.get_text(" ", strip=True)
            for marker in candidate.select(".b_adLabel, .ads_label, .sponsored, .label")
        ).lower()
        return any(token in marker_text for token in {"ad", "ads", "sponsored"})

    def _infer_source(self, url: str) -> str:
        """从 URL 提炼域名。"""
        parsed = urlparse(url)
        return parsed.netloc or "bing"
