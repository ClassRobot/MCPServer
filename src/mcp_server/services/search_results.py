"""浏览器原始搜索候选结果的过滤、清洗与规范化转换的业务服务层。

该模块提供对不同搜索引擎返回的原始结果结构体进行广告剔除、
非自然排名筛选、空标题与空 URL 拦截、URL 去重以及去除追踪参数的逻辑处理。
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from mcp_server.config import SearchFilterSettings
from mcp_server.schemas import RawSearchResult, SearchResult


class SearchResultFilter:
    """搜索结果过滤器类。

    提供对网页检索出的原始候选结果进行去重、广告拦截、URL 参数净化和自然排名重排名的核心逻辑。
    """

    def __init__(self, settings: SearchFilterSettings) -> None:
        """初始化搜索结果过滤器。

        Args:
            settings (SearchFilterSettings): 过滤策略与广告开关的参数配置集。
        """
        self._settings = settings

    def filter_results(
        self,
        raw_results: list[RawSearchResult],
        *,
        filter_ads: bool,
        strict_natural_results_only: bool | None = None,
    ) -> tuple[list[SearchResult], int]:
        """将底层搜索引擎返回的原始 RawSearchResult 候选转换为规范稳定的展示用 SearchResult。

        在此过程中，会应用去重算法、广告及非自然排名过滤规则，并为过审后的条目重新分配连续的名次(Rank)。

        Args:
            raw_results (list[RawSearchResult]): 底层搜索引擎爬取到的原始结果候选列表。
            filter_ads (bool): 是否在该次请求中强制开启广告拦截。
            strict_natural_results_only (bool | None): 是否仅保留完全自然排名的搜索项。若为 None，则自适应配置文件的全局默认设置。

        Returns:
            tuple[list[SearchResult], int]: 由 (已完成清洗重排名的搜索结果列表, 被拦截过滤掉的垃圾条目总计数) 构成的二元组。
        """
        strict_mode = (
            self._settings.strict_natural_results_only
            if strict_natural_results_only is None
            else strict_natural_results_only
        )
        filtered_count = 0
        seen_urls: set[str] = set()
        structured_results: list[SearchResult] = []

        for raw_result in raw_results:
            # 1. 净化并对齐 URL 格式，为精确去重奠定基础
            normalized_url = self._normalize_url(raw_result.url)
            
            # 2. 如果开启广告拦截且当前条目被标记为广告，则予以剔除
            if filter_ads and self._settings.ads_enabled and raw_result.is_ad:
                filtered_count += 1
                continue
                
            # 3. 严格模式拦截：若只保留自然搜索项而当前属于推荐/推广等非自然内容，则予以剔除
            if strict_mode and not raw_result.is_natural:
                filtered_count += 1
                continue
                
            # 4. 空数据完整性检验：防止爬取到空标题或空链接引发前端渲染空白卡片
            if not raw_result.title.strip() or not normalized_url:
                filtered_count += 1
                continue
                
            # 5. 精确去重检查：规避不同搜索引擎抓取结果集在不同源站或在合并时出现冗余
            if normalized_url in seen_urls:
                filtered_count += 1
                continue

            seen_urls.add(normalized_url)
            # 6. 为过滤合格的数据生成重新分配 Rank 索引的标准结构，名次从 1 开始
            structured_results.append(
                SearchResult(
                    rank=len(structured_results) + 1,
                    title=raw_result.title.strip(),
                    url=normalized_url,
                    snippet=raw_result.snippet.strip() if raw_result.snippet else None,
                    source=raw_result.source,
                )
            )

        return structured_results, filtered_count

    def _normalize_url(self, url: str) -> str:
        """对 URL 实施规范化对齐，剥离各类分析追踪尾巴，保证去重逻辑的绝对稳定性。

        Args:
            url (str): 原始待洗的 URL 字符串。

        Returns:
            str: 格式规整化且去除了 UTM 等垃圾参数的 URL 字符串；若 URL 不合规，则回退返回空字符串。
        """
        if not url:
            return ""

        parsed = urlparse(url.strip())
        if not parsed.netloc:
            return ""

        # 剥离诸如 utm_source、utm_medium、gclid 等用于广告点击归因追踪的冗余 query 参数，保证相同的实际页面拥有确定性的 URL 签名
        cleaned_query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if key.lower()
                not in {"utm_source", "utm_medium", "utm_campaign", "gclid", "fbclid"}
            ]
        )
        # 统一将 scheme 和 netloc 转为小写，并重组 URL 剥离无意义锚点(hash fragment)
        normalized = parsed._replace(
            scheme=(parsed.scheme or "https").lower(),
            netloc=parsed.netloc.lower(),
            query=cleaned_query,
            fragment="",
        )
        return urlunparse(normalized)

