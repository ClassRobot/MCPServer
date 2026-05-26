"""百度搜索引擎页面解析与数据适配器。

驱动 Playwright 浏览器会话访问百度搜索，等待核心节点渲染，
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


class BaiduSearchProvider:
    """百度搜索适配器类。

    主要负责构建百度搜索 URL，并在已存在的浏览器页面会话中执行导航与内容提取。
    """

    def __init__(self, settings: BrowserSettings) -> None:
        """初始化百度搜索适配器。

        Args:
            settings (BrowserSettings): 浏览器通用运行配置。
        """
        self._settings = settings

    def build_search_url(self, query: str) -> str:
        """构建百度网页搜索的 WD 请求 URL。

        Args:
            query (str): 搜索关键词。

        Returns:
            str: 编码后的百度搜索完整 URL。
        """
        return f"https://www.baidu.com/s?wd={quote_plus(query)}"

    async def search(
        self,
        session_manager: BrowserSessionManager,
        session_id: str,
        query: str,
    ) -> list[RawSearchResult]:
        """在指定的浏览器会话中执行百度搜索并返回解析结果。

        Args:
            session_manager (BrowserSessionManager): 浏览器会话管理器。
            session_id (str): 目标会话的唯一标识 ID。
            query (str): 搜索关键词。

        Returns:
            list[RawSearchResult]: 结构化候选搜索结果列表。
        """
        page = await session_manager.get_page(session_id)
        
        # 1. 导航到目标搜索页，等待 DOM 内容加载完成以保证响应时效
        await page.goto(
            self.build_search_url(query),
            wait_until="domcontentloaded",
            timeout=self._settings.timeout_ms,
        )
        
        try:
            # 2. 等待百度搜索结果的主容器元素 (#content_left) 附加到 DOM 中
            await page.wait_for_selector(
                "#content_left",
                state="attached",
                timeout=self._settings.timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("百度搜索结果主容器 '#content_left' 未在超时限制内渲染完成。") from exc
            
        html = await page.content()
        return self.parse_results(html)

    def parse_results(self, html: str) -> list[RawSearchResult]:
        """使用 BeautifulSoup 对百度搜索结果 HTML 进行清洗提纯。

        Args:
            html (str): 百度搜索结果页面的完整 HTML 源码。

        Returns:
            list[RawSearchResult]: 解析出的搜索项（包含自然结果与广告标记）。
        """
        soup = BeautifulSoup(html, "html.parser")
        results_root = soup.select_one("#content_left")
        if results_root is None:
            return []

        parsed_results: list[RawSearchResult] = []
        for candidate in self._iter_candidates(results_root):
            classes = set(candidate.get("class", []))
            
            # 1. 提取标题和目标跳转链接
            title_node = candidate.select_one("h3") or candidate.select_one(".t")
            anchor = title_node.select_one("a[href]") if title_node else candidate.select_one("a[href]")
            
            title = anchor.get_text(" ", strip=True) if anchor else ""
            url = anchor.get("href", "").strip() if anchor else ""
            
            # 2. 提取摘要正文（百度不同模版类名的自适应选择器）
            snippet_node = (
                candidate.select_one(".content-abstract") or 
                candidate.select_one(".c-abstract") or
                candidate.select_one(".c-span18") or
                candidate.select_one(".c-span-all")
            )
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None
            
            # 3. 提取展示的源网站域名
            source_node = candidate.select_one(".c-showurl") or candidate.select_one(".g")
            site_name = source_node.get_text(" ", strip=True) if source_node else None
            source = self._infer_source(url) if url else "baidu"

            # 4. 调用敏感广告识别及自然结果判别规则
            is_ad = self._looks_like_ad(candidate, classes)
            is_natural = ("result" in classes or "result-op" in classes) and not is_ad

            parsed_results.append(
                RawSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source,
                    is_ad=is_ad,
                    is_natural=is_natural,
                )
            )
        return parsed_results

    def _iter_candidates(self, results_root: Tag) -> Iterable[Tag]:
        """迭代抽取百度主容器中的有效结果卡片节点，自动过滤掉无关组件。

        【过滤算法说明】：
        - 百度搜索页底部的相关搜索块（id 为 "rs"）以及一些推荐提示框（带有 class "hint"），
          需要在此处剔除，只保留真实的搜索项。
        """
        for child in results_root.find_all("div", recursive=False):
            if not isinstance(child, Tag):
                continue
            if child.get("id") == "rs" or "hint" in child.get("class", []):
                continue
            yield child

    def _looks_like_ad(self, candidate: Tag, classes: set[str]) -> bool:
        """多重特征混合判定规则，检测百度搜索结果中的推广广告。

        【广告检测规则说明】：
        1. 检查节点内任意带有灰色标注的 span 文本，如果明确含有 "广告" 二字，判为广告。
        2. 百度商业广告节点通常带有 `data-tu` 属性或者样式类中含有 `m` 标识，一并拦截。
        """
        ad_labels = candidate.select(".c-gray") + candidate.select("span")
        for label in ad_labels:
            if "广告" in label.get_text():
                return True
        if candidate.get("data-tu") or "m" in classes:
            return True
        return False

    def _infer_source(self, url: str) -> str:
        """从跳转 URL 中提炼提取出源站域名标识。"""
        if not url:
            return "baidu"
        try:
            parsed = urlparse(url)
            return parsed.netloc or "baidu"
        except Exception:
            return "baidu"
