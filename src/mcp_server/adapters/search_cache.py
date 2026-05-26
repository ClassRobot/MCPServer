"""基于本地物理文件系统的有状态浏览器搜索结果缓存中心。

对网络检索返回的结构化结果进行本地磁盘 JSON 持久化，支持定时失效（TTL）校验，
并内置基于文件系统 stat 元数据的轻量级 LRU（最近最少使用）缓存剪枝淘汰算法。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mcp_server.config import SearchCacheSettings
from mcp_server.schemas import BrowserSearchResponse, SearchResult


class SearchCacheStore:
    """有界磁盘缓存存储器类。

    将结构化的 BrowserSearchResponse 结果对象以 JSON 密文/明文持久化在本地物理磁盘中。
    """

    def __init__(self, settings: SearchCacheSettings) -> None:
        """初始化缓存存储器。

        Args:
            settings (SearchCacheSettings): 本地搜索缓存的相关配置。
        """
        self._settings = settings

    def build_cache_key(
        self,
        *,
        provider: str,
        normalized_query: str,
        max_results: int,
        filter_ads: bool,
        include_summary: bool,
    ) -> str:
        """为高层浏览器网络搜索请求构建一个确定性且抗冲突的稳定缓存 Key。

        【缓存 Key 计算算法】：
        1. 将所有可能影响搜索结果的参数包收拢进一个 dict 中。
        2. 采用 `sort_keys=True` 确保字典键顺序一致，`ensure_ascii=False` 保证中文字符直接序列化，
           使用 `json.dumps` 导出唯一的确定性文本流。
        3. 调用 SHA-256 算法计算散列值，输出唯一的 64 位十六进制摘要串（Hex Digest）。
        """
        payload = json.dumps(
            {
                "provider": provider,
                "query": normalized_query,
                "max_results": max_results,
                "filter_ads": filter_ads,
                "include_summary": include_summary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> BrowserSearchResponse | None:
        """若物理缓存文件存在且未过期，则反序列化并返回缓存结果。

        Args:
            cache_key (str): 通过 build_cache_key 计算出的缓存 Key。

        Returns:
            BrowserSearchResponse | None: 反序列化后的结果对象。若失效或不存在则返回 None。
        """
        if not self._settings.enabled:
            return None

        cache_file = self._cache_file(cache_key)
        if not cache_file.exists():
            return None

        try:
            with cache_file.open("r", encoding="utf-8") as cache_handle:
                payload = json.load(cache_handle)
        except (OSError, json.JSONDecodeError):
            # 如果文件损坏或读取异常，直接安全清理该失效缓存
            cache_file.unlink(missing_ok=True)
            return None

        # 校验内部写入的硬时间戳 expires_at 是否已过期
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if expires_at <= datetime.now(UTC):
            cache_file.unlink(missing_ok=True)
            return None

        response_payload = payload["response"]
        return BrowserSearchResponse(
            query=response_payload["query"],
            provider=response_payload["provider"],
            summary=response_payload["summary"],
            cache_hit=True,
            filtered_count=response_payload["filtered_count"],
            results=[
                SearchResult(
                    rank=result["rank"],
                    title=result["title"],
                    url=result["url"],
                    snippet=result["snippet"],
                    source=result["source"],
                )
                for result in response_payload["results"]
            ],
        )

    def set(self, cache_key: str, response: BrowserSearchResponse) -> None:
        """将新的结构化搜索结果写入本地物理磁盘并执行剪枝动作。

        Args:
            cache_key (str): 散列缓存 Key。
            response (BrowserSearchResponse): 待持久化的响应对象。
        """
        if not self._settings.enabled:
            return

        cache_file = self._cache_file(cache_key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (
                datetime.now(UTC) + timedelta(seconds=self._settings.ttl_sec)
            ).isoformat(),
            "response": asdict(response),
        }
        with cache_file.open("w", encoding="utf-8") as cache_handle:
            json.dump(payload, cache_handle, ensure_ascii=False, indent=2)
            
        # 写入后立即触发剪枝清理算法，保证缓存容量是有界的
        self.prune()

    def prune(self) -> None:
        """对超过最大容量限制（max_entries）或已过期的缓存文件进行裁剪清理。

        【高性能 LRU 剪枝算法说明】：
        - 性能折中策略：
          为了极致的运行效率，prune() 会直接读取文件的最后修改时间 `st_mtime`
          和当前的缓存 `ttl_sec` 来直接判定失效，从而**完全免除了打开并解析每个 JSON 文件
          的巨大 O(N) 磁盘 I/O 开销**。
        - 剪枝执行逻辑：
          1. 遍历缓存目录下的所有 *.json 文件，调用 os.stat。
          2. 若文件修改时间早于过期限制，直接进行 `unlink` 物理删除。
          3. 若未过期，将其放入活跃文件列表中（记录 st_mtime 和文件路径）。
          4. 检查活跃列表长度，若依然超过 `max_entries` 限制，
             则将列表按修改时间降序（最近最常使用在前）排序，并将尾部的老旧文件执行 `unlink` 淘汰。
        """
        cache_dir = self._settings.base_dir
        if not cache_dir.exists():
            return

        now_ts = datetime.now(UTC).timestamp()
        ttl = self._settings.ttl_sec

        try:
            cache_files = list(cache_dir.glob("*.json"))
        except OSError:
            return

        valid_files: list[tuple[float, Path]] = []
        for cache_file in cache_files:
            try:
                stat = cache_file.stat()
                # 判定文件是否已存在过久
                if now_ts - stat.st_mtime > ttl:
                    cache_file.unlink(missing_ok=True)
                else:
                    valid_files.append((stat.st_mtime, cache_file))
            except OSError:
                continue

        # 超过上限时，按时间先后顺序，末尾淘汰最老旧的数据
        if len(valid_files) > self._settings.max_entries:
            valid_files.sort(key=lambda item: item[0], reverse=True)
            for _, extra_file in valid_files[self._settings.max_entries :]:
                extra_file.unlink(missing_ok=True)

    def _cache_file(self, cache_key: str) -> Path:
        """计算得出具体 Key 对应的本地物理 JSON 文件路径。"""
        return self._settings.base_dir / f"{cache_key}.json"
