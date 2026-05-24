# Tools Guide

本目录管理所有可供客户端显式调用的 MCP 工具（Tools）。

## 工具模块构成
每个独立的工具模块最低限度应包含：
1. **核心逻辑函数**: 实现工具的具体功能。
2. **`register_*_tools(mcp: FastMCP)`**: 统一的能力注册函数，用于在 `app.py` 中被加载。

## 设计与新增指南
- **高内聚职责**: 工具函数仅处理输入校验、参数映射与最终结果组装，严禁在此实现复杂的第三方逻辑调度。
- **按域命模块**: 新增工具应按领域（如 `browser.py`）建立独立文件，并在 `__init__.py` 中暴露出注册函数。
- **稳定性规范**: 接口必须声明明确的类型提示（Type Hints），并提供相应的测试文件。若出现跨工具复用或复杂状态，应及时重构至服务层。

---

## 核心工具接口列表 (API Reference)

### 1. 内容与图片渲染工具

#### `render_content_to_image`
将 HTML 或 Markdown 原文渲染为高品质 PNG 图片。
- **主要参数**:
  - `content` (str): 需要渲染的 HTML 标签或 Markdown 正文。
  - `input_format` (Literal["html", "markdown"]): 输入格式类型。
  - `theme` (Literal["light", "dark"], 默认 `"light"`): 图片明暗视觉主题。
  - `width` (int, 默认 `800`): 浏览器视口宽度（像素）。
  - `height` (int, 可选, 默认 `None`): 浏览器视口高度。若为 `None`，则根据内容自适应无限延长，精确包裹真实内容（去除底部多余空白）。
  - `output_path` (str, 可选): 指定的本地图片文件名或路径（如 `"report.png"`）。
- **返回结构 (`RenderImageResult`)**:
  - `file_path` (str): 渲染图持久化的本地绝对物理路径。
  - `base64_image` (str): 渲染图片的 Base64 编码字符串（免去客户端二次读盘）。
  - `width` / `height` (int) / `input_format` (str): 渲染基础元数据。

---

### 2. 高阶浏览器搜索工具

#### `browser_search`
驱动 Headless 浏览器调用搜索引擎（如 Bing），并对结果进行结构化提纯。
- **主要参数**:
  - `query` (str): 搜索关键词。
  - `provider` (str, 默认 `"bing"`): 搜索引擎源。
  - `max_results` (int, 可选): 返回的自然搜索结果上限。
  - `include_summary` (bool, 默认 `False`): 是否提取并附加页面正文摘要。
  - `use_cache` (bool, 默认 `True`): 是否命中本地持久化搜索缓存。
  - `force_refresh` (bool, 默认 `False`): 是否强制穿透缓存刷新。
  - `filter_ads` (bool, 默认 `True`): 是否过滤搜索引擎广告推荐链接。
- **返回结构 (`BrowserSearchResponse`)**:
  - `query` / `provider` (str): 输入凭证。
  - `results` (list[SearchResult]): 包含 `rank`, `title`, `url`, `snippet`, `source` 的结构化自然搜索列表。
  - `summary` (str | None) / `cache_hit` (bool) / `filtered_count` (int).

---

### 3. 低阶浏览器会话与网页自动化工具

| 工具名称 | 核心职责 | 输入参数 | 典型返回字段 |
| :--- | :--- | :--- | :--- |
| **`browser_create_session`** | 创建复用浏览器会话。 | `headless` (bool, 可选) | `session_id` (str), `headless` (bool) |
| **`browser_open`** | 在指定会话中载入目标 URL。 | `session_id` (str), `url` (str) | `session_id`, `url`, `title` |
| **`browser_fill`** | 在指定会话中填充输入框。 | `session_id`, `selector`, `value`, `clear` (bool, 默认 `True`) | `session_id`, `selector`, `value` |
| **`browser_click`** | 在指定会话中点击 DOM 元素。 | `session_id`, `selector`, `wait_for_network_idle` (bool) | `session_id`, `url`, `title` |
| **`browser_extract`** | 从当前会话提取正文或超链接。 | `session_id`, `selector` (可选), `include_links` (bool), `max_links` (int) | `session_id`, `title`, `url`, `text` (正文), `links` (解析外链) |
| **`browser_close_session`** | 主动释放并销毁浏览器会话。 | `session_id` (str) | `session_id`, `closed` (bool) |



