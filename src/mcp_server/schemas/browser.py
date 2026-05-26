"""基于浏览器引擎网页检索及底层页面元素提取的共享数据结构定义。

所有数据类仅使用 `slots=True` 提高属性访问效率并限制动态属性绑定，故意未设为 `frozen=True` 以允许状态的原地修改。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchResult:
    """最终回传给 MCP 客户端的规范化自然网页搜索结果结构体。"""

    rank: int
    title: str
    url: str
    snippet: str | None
    source: str


@dataclass(slots=True)
class BrowserSearchResponse:
    """高层浏览器网页检索工具返回的规范化端到端响应结果。"""

    query: str
    provider: str
    results: list[SearchResult]
    summary: str | None
    cache_hit: bool
    filtered_count: int


@dataclass(slots=True)
class BrowserSessionInfo:
    """底层有状态浏览器会话生命周期的只读元数据结构。"""

    session_id: str
    headless: bool


@dataclass(slots=True)
class BrowserExtractLink:
    """从页面元素或 DOM 片段中爬取解析出来的超链接元数据。"""

    text: str
    url: str


@dataclass(slots=True)
class BrowserExtractResult:
    """底层浏览器页面读取提取工具生成的结构化快照结果。"""

    session_id: str
    title: str
    url: str
    text: str
    links: list[BrowserExtractLink] = field(default_factory=list)


@dataclass(slots=True)
class RawSearchResult:
    """底层搜索引擎提供商直接提取的、未经清洗、去重和广告过滤的原始候选搜索结果。"""

    title: str
    url: str
    snippet: str | None
    source: str
    is_ad: bool = False
    is_natural: bool = True
