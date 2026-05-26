"""底层浏览器自动化及高层网页搜索引擎检索的 MCP 工具接口层。

该模块将 Playwright 有状态浏览器会话操作、网页截图及缓存检索服务，
包装暴露为符合 MCP 标准规范的工具接口，供大语言模型客户端调用。
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.adapters.browser_session import BrowserSessionManager
from mcp_server.config import ServerSettings
from mcp_server.services.browser_search import BrowserSearchService
from mcp_server.tool_logging import log_mcp_tool


def register_browser_tools(
    mcp: FastMCP,
    *,
    settings: ServerSettings,
    browser_search_service: BrowserSearchService,
    session_manager: BrowserSessionManager,
) -> None:
    """注册浏览器搜索引擎检索及有状态浏览器底层操作相关的 MCP 工具。

    Args:
        mcp (FastMCP): FastMCP 应用程序实例。
        settings (ServerSettings): 服务端全局核心配置对象。
        browser_search_service (BrowserSearchService): 网页多引擎高级搜索调度服务。
        session_manager (BrowserSessionManager): 有状态浏览器会话生命周期管理器。
    """

    @mcp.tool(
        name="browser_search",
        description=(
            "Execute a comprehensive browser-driven search using public search engines."
            " Returns structured search results including titles, URLs, and snippets."
            " Best used for gathering real-time information from the web."
        ),
    )
    @log_mcp_tool("browser_search", settings.logging)
    async def browser_search(
        query: str,
        provider: str = "bing",
        max_results: int | None = None,
        include_summary: bool = False,
        use_cache: bool = True,
        force_refresh: bool = False,
        filter_ads: bool = True,
    ) -> list[Any]:
        """运行基于真实浏览器渲染的网页检索并返回结果包。

        Args:
            query (str): 待检索的用户自然语言词组或提问。
            provider (str): 搜索引擎名称，当前支持 'bing' 或 'baidu'。
            max_results (int | None): 最高保留的自然搜索项数量。
            include_summary (bool): 是否返回前三条自然排名结果智能组合而成的简明摘要。
            use_cache (bool): 是否启用磁盘 LRU 缓存拦截逻辑。
            force_refresh (bool): 是否强制透传缓存直达源站刷新。
            filter_ads (bool): 是否应用商业推广/垃圾广告清洗过滤器。

        Returns:
            list[Any]: 包含序列化后搜索自然项及元数据的 MCP 文本对象列表。
        """
        from mcp.types import TextContent

        # 调用核心领域服务执行高层级多引擎聚合网页搜索
        response = await browser_search_service.search(
            query=query,
            provider=provider or settings.browser_search.browser.default_provider,
            max_results=max_results,
            include_summary=include_summary,
            use_cache=use_cache,
            force_refresh=force_refresh,
            filter_ads=filter_ads,
        )

        lines = [f"Search results for '{query}' via {response.provider}:", ""]
        if not response.results:
            lines.append("No results found.")
        else:
            # 循环组装自然排名结果并展示 title, url, snippet
            for i, res in enumerate(response.results, 1):
                lines.append(f"{i}. **{res.title}**")
                lines.append(f"   URL: {res.url}")
                if res.snippet:
                    lines.append(f"   Snippet: {res.snippet}")
                lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    @mcp.tool(
        name="browser_create_session",
        description=(
            "Initialize a new stateful browser session. "
            "Allows for complex multi-step interactions (e.g., login, form filling). "
            "Can optionally load a saved storage state (cookies, localStorage) by state_name."
        ),
        structured_output=True,
    )
    @log_mcp_tool("browser_create_session", settings.logging)
    async def browser_create_session(
        headless: bool | None = None,
        state_name: str | None = None,
    ) -> dict[str, Any]:
        """初始化一个用于多步骤复杂交互的有状态浏览器沙箱会话。

        Args:
            headless (bool | None): 是否以无头模式启动浏览器环境。若为 None 则使用默认设置。
            state_name (str | None): 可选的之前成功备份到磁盘的会话状态名（读取 Cookie 与 LocalStorage）。

        Returns:
            dict[str, Any]: 包含新建会话 session_id 及运行参数的元数据字典。
        """
        storage_state_path = None
        if state_name:
            import re

            # 执行严格的正则防御性校验，防范文件名遍历/命令注入
            if not re.match(r"^[a-zA-Z0-9_-]+$", state_name):
                raise ValueError(
                    "Invalid state_name. Use only letters, numbers, underscores, and hyphens."
                )

            state_file = settings.sessions_dir / f"{state_name}.json"
            if state_file.exists():
                storage_state_path = str(state_file)

        # 调配有状态会话管理器拉起底层的 Pyppeteer/Playwright 实例
        session_info = await session_manager.create_session(
            headless=headless,
            storage_state_path=storage_state_path,
        )
        return asdict(session_info)

    @mcp.tool(
        name="browser_open",
        description="Navigate to a specific URL within an active browser session.",
        structured_output=True,
    )
    @log_mcp_tool("browser_open", settings.logging)
    async def browser_open(session_id: str, url: str) -> dict[str, Any]:
        """在当前存活的有状态浏览器会话中导航跳转到指定 URL。

        Args:
            session_id (str): 有效的浏览器会话标识 ID。
            url (str): 目标网站的绝对超链接。

        Returns:
            dict[str, Any]: 包含当前页面加载后 URL 及 Title 等基础信息的字典。
        """
        return await session_manager.open(session_id, url)

    @mcp.tool(
        name="browser_fill",
        description="Type text into an input field or textarea identified by a CSS selector.",
        structured_output=True,
    )
    @log_mcp_tool("browser_fill", settings.logging)
    async def browser_fill(
        session_id: str,
        selector: str,
        value: str,
        clear: bool = True,
    ) -> dict[str, Any]:
        """定位特定输入框或文本域元素并安全模拟输入指定字符内容。

        Args:
            session_id (str): 有效的浏览器会话标识 ID。
            selector (str): 用于精准过滤元素的 CSS 选择符表达式。
            value (str): 需要录入的文本串。
            clear (bool): 是否在键入字符前先清空当前表单框。默认值为 True。

        Returns:
            dict[str, Any]: 提示写入结果成功状态字典。
        """
        return await session_manager.fill(session_id, selector, value, clear=clear)

    @mcp.tool(
        name="browser_click",
        description=(
            "Click a button, link, or other clickable element identified by a CSS selector."
        ),
        structured_output=True,
    )
    @log_mcp_tool("browser_click", settings.logging)
    async def browser_click(
        session_id: str,
        selector: str,
        wait_for_network_idle: bool = True,
    ) -> dict[str, Any]:
        """模拟物理鼠标左键点击选中的 DOM 节点（如按钮、链接等）。

        Args:
            session_id (str): 有效的浏览器会话标识 ID。
            selector (str): CSS 选择符表达式。
            wait_for_network_idle (bool): 点击动作完成后，是否安全等待页面网络载入空闲。默认值为 True。

        Returns:
            dict[str, Any]: 点击操作成功与否字典。
        """
        return await session_manager.click(
            session_id,
            selector,
            wait_for_network_idle=wait_for_network_idle,
        )

    @mcp.tool(
        name="browser_extract",
        description=(
            "Extract structured text and links from the current page. "
            "Can be scoped to a specific element using a CSS selector."
        ),
    )
    @log_mcp_tool("browser_extract", settings.logging)
    async def browser_extract(
        session_id: str,
        selector: str | None = None,
        include_links: bool = False,
        max_links: int = 10,
    ) -> list[Any]:
        """深度提取指定页面当前渲染状态下的纯文本和超链接表单集合。

        Args:
            session_id (str): 有效的浏览器会话标识 ID。
            selector (str | None): 可选的 CSS 精准定位容器，若未提供则默认对全局 document 提取。
            include_links (bool): 是否同时把元素内部的 <a> 链接列表进行统计收集。
            max_links (int): 单个页面最高返回的外部超链接数，默认值为 10。

        Returns:
            list[Any]: MCP 标准富文本包裹提取结果。
        """
        from mcp.types import TextContent

        extracted = await session_manager.extract(
            session_id=session_id,
            selector=selector,
            include_links=include_links,
            max_links=max_links,
        )

        lines = [
            f"Extracted from: {extracted.url}",
            f"Title: {extracted.title}",
            "",
            extracted.text,
        ]

        # 如果开启了提取链接且链接列表非空，按规范格式化输出
        if extracted.links:
            lines.append("\n--- Links ---")
            for link in extracted.links:
                lines.append(f"- {link.text}: {link.url}")

        return [TextContent(type="text", text="\n".join(lines))]

    @mcp.tool(
        name="browser_close_session",
        description="Close an existing browser session.",
        structured_output=True,
    )
    @log_mcp_tool("browser_close_session", settings.logging)
    async def browser_close_session(session_id: str) -> dict[str, Any]:
        """优雅关闭运行中的有状态浏览器会话并回收物理进程及相关端口。

        Args:
            session_id (str): 待关闭的浏览器会话标识 ID。

        Returns:
            dict[str, Any]: 回收成功与否的字典。
        """
        return await session_manager.close_session(session_id)

    @mcp.tool(
        name="browser_save_session_state",
        description="Save the storage state (cookies, localStorage) of an active session to disk.",
        structured_output=True,
    )
    @log_mcp_tool("browser_save_session_state", settings.logging)
    async def browser_save_session_state(
        session_id: str,
        state_name: str,
    ) -> dict[str, Any]:
        """将当前会话缓存的 Cookie、LocalStorage 等敏感持久化状态序列化备份至指定 json 文件。

        Args:
            session_id (str): 有效的有状态会话 ID。
            state_name (str): 物理磁盘文件名（如 'my_login'）。

        Returns:
            dict[str, Any]: 磁盘保存的完整绝对路径及操作成功字典。
        """
        import re

        # 正则防注入边界测试
        if not re.match(r"^[a-zA-Z0-9_-]+$", state_name):
            raise ValueError(
                "Invalid state_name. Use only letters, numbers, underscores, and hyphens."
            )

        settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        dest_path = settings.sessions_dir / f"{state_name}.json"

        await session_manager.save_storage_state(session_id, str(dest_path))
        return {
            "session_id": session_id,
            "state_name": state_name,
            "saved_path": str(dest_path),
            "success": True,
        }

    @mcp.tool(
        name="browser_screenshot_url",
        description=(
            "Capture a high-quality visual screenshot of a given URL. "
            "Supports rendering either a specific height or full scrollable height."
        ),
    )
    @log_mcp_tool("browser_screenshot_url", settings.logging)
    async def browser_screenshot_url(
        url: str,
        width: int = 1200,
        height: int | None = None,
        session_id: str | None = None,
    ) -> list[Any]:
        """对任意指定公开或授权的 URL 执行高品质视觉抓拍（截屏），可自适应渲染整页。

        Args:
            url (str): 目标网页 URL 链接。
            width (int): 浏览器视口宽度（像素），默认值为 1200。
            height (int | None): 浏览器视口高度（像素）。若为 None，则自适应滚动捕获页面物理全高度。
            session_id (str | None): 可选的复用已登录会话 ID。若未提供，将新建一个临时无头会话。

        Returns:
            list[Any]: 由说明文本和 base64 图像字节包装的 MCP 混合资产列表。
        """
        import base64
        from uuid import uuid4

        from mcp.types import ImageContent, TextContent

        is_temp_session = False
        active_session_id = session_id

        # 1. 无复用会话时，动态拉起一个临时隔离的无头沙箱
        if not active_session_id:
            session_info = await session_manager.create_session(headless=True)
            active_session_id = session_info.session_id
            is_temp_session = True

        try:
            page = await session_manager.get_page(active_session_id)

            initial_height = height if height is not None else 800
            await page.set_viewport_size({"width": width, "height": initial_height})

            # 2. 页面重定向并强效等待基本 DOM 及样式载入就绪
            await page.goto(
                url, wait_until="load", timeout=settings.browser_search.browser.timeout_ms
            )
            try:
                # 尽力加载，如果网络空闲检测超时则可以安全忽略（因大部分异步 tracking 并不影响视觉呈现）
                await page.wait_for_load_state(
                    "networkidle", timeout=settings.browser_search.browser.timeout_ms
                )
            except Exception:
                pass

            # 3. 自适应整页高度捕获，消除冗长尾白
            if height is None:
                content_height = await page.evaluate("() => document.documentElement.scrollHeight")
                viewport_height = max(content_height, 1)
                await page.set_viewport_size({"width": width, "height": viewport_height})
                screenshot_bytes = await page.screenshot(full_page=False, type="png")
                actual_height = viewport_height
            else:
                screenshot_bytes = await page.screenshot(full_page=True, type="png")
                actual_height = height

        finally:
            # 4. 无论何种状况，必须销毁临时拉起的浏览器页签句柄
            if is_temp_session:
                await session_manager.close_session(active_session_id)

        # 5. 后台安全异步写盘备份截图
        output_dir = settings.render_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        resolved_path = output_dir / f"screenshot_{uuid4().hex[:8]}.png"

        import asyncio

        await asyncio.to_thread(resolved_path.write_bytes, screenshot_bytes)

        base64_data = base64.b64encode(screenshot_bytes).decode("utf-8")

        description = (
            f"Screenshot of {url} captured successfully.\n"
            f"Dimensions: {width}x{actual_height}px\n"
            f"Resource URI: render://{resolved_path.name}"
        )

        return [
            TextContent(type="text", text=description),
            ImageContent(
                type="image",
                data=base64_data,
                mimeType="image/png",
            ),
        ]
