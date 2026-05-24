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

### 0. 基础设施验证工具 (Database Integration)

#### `database_record_query`
把一条查询记录写入当前配置的数据库，用于验证 MCP Tool -> Service -> Repository -> Database 的闭环是否打通。

#### `database_list_query_history`
读取最近写入的查询历史，用于最小数据库读链路验证与基础排障。

---

### 1. 内容与图片渲染工具 (HTML/Markdown to Image)

#### `render_content_to_image`
将 HTML 或 Markdown 原文渲染为高品质 PNG 图片。
- **主要参数**:
  - `content` (str): 需要渲染的 HTML 标签或 Markdown 正文。
  - `input_format` (Literal["html", "markdown"]): 输入格式类型。
  - `theme` (Literal["light", "dark"], 默认 `"light"`): 图片明暗视觉主题。
  - `width` (int, 默认 `800`): 浏览器视口宽度（像素）。
  - `height` (int, 可选, 默认 `None`): 浏览器视口高度。若为 `None`，则根据内容自适应无限延长，精确包裹真实内容（去除底部多余空白）。
  - `output_path` (str, 可选): 指定的本地图片文件名或路径。

---

### 2. 数据图表动态生成器 (ECharts Data Visualizer)

#### `render_data_chart`
将结构化数据（JSON）自动转化为高对比度、极其精美的数据图表图片（PNG），基于 Apache ECharts 5.5.0 进行硬件渲染。
- **主要参数**:
  - `chart_type` (Literal["line", "bar", "pie", "radar", "scatter"]): 图表可视化类型。
  - `data` (dict): 数据载荷。
    - 基础模式: `{ "labels": ["Mon", "Tue"], "datasets": [{ "label": "Sales", "data": [120, 200] }] }`。
    - 高级模式: 支持直接在 `"option"` 键下传入原生 ECharts Option JSON，享有无级定制自由度。
  - `title` (str, 可选): 图表标题。
  - `theme` (Literal["light", "dark"], 默认 `"light"`): 图表视觉配色主题（HSL渐变色与拟物阴影）。
  - `width` (int, 默认 `800`): 渲染图片宽度。
  - `height` (int, 默认 `600`): 渲染图片高度。
  - `output_path` (str, 可选): 指定的本地图片输出路径。

---

### 3. 高阶浏览器搜索工具 (Structured Web Search)

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

---

### 4. 低阶浏览器会话与网页自动化工具 (RPA & Keepalive)

| 工具名称 | 核心职责 | 输入参数 | 典型返回与说明 |
| :--- | :--- | :--- | :--- |
| **`browser_create_session`** | 创建或唤醒复用浏览器会话。 | `headless` (bool, 可选), `state_name` (str, 可选) | 传入 `state_name` 时自动从硬盘载入先前导出的 Cookie/LocalStorage (StorageState)，快速维持登录态。 |
| **`browser_save_session_state`** | 导出当前浏览器会话的登录状态。 | `session_id` (str), `state_name` (str) | 安全保存当前会话的 StorageState 为 JSON，供后续 `create_session` 复用。 |
| **`browser_screenshot_url`** | 网页视觉快照捕获。 | `url` (str), `width` (int), `height` (int, 可选), `session_id` (可选) | 支持传入 `session_id` 在已登录状态下截图；不传入则自动拉起临时沙箱会话截图并即时销毁。 |
| **`browser_open`** | 在指定会话中载入目标 URL。 | `session_id` (str), `url` (str) | 载入并等待 `networkidle`，防止异步图片或字体漏渲染。 |
| **`browser_fill`** | 在指定会话中填充输入框。 | `session_id`, `selector`, `value`, `clear` (默认 `True`) | 典型 RPA 操作。 |
| **`browser_click`** | 在指定会话中点击 DOM 元素。 | `session_id`, `selector`, `wait_for_network_idle` | 支持点击后智能阻断等待网络静默。 |
| **`browser_extract`** | 从当前会话提取正文或超链接。 | `session_id`, `selector`, `include_links`, `max_links` | 提供 BeautifulSoup 极速清洗。 |
| **`browser_close_session`** | 主动释放并销毁浏览器会话。 | `session_id` (str) | 强力内存及浏览器实例释放。 |

---

### 5. 多模态本地 PDF 文档阅读器 (Poppler-free PDF Reader)

#### `browser_render_pdf`
高清光栅化渲染指定页或全部页面，生成 PNG 文件并输出 Base64 流，供大模型进行多模态“视觉”理解。
- **主要参数**:
  - `pdf_path` (str): 本地绝对路径或项目相对路径。
  - `pages` (list[int], 可选): 1-indexed 的页码列表（如 `[1, 3]`）。不传则默认渲染全量页面。
  - `dpi` (int, 默认 `150`): 视觉渲染精度分辨率，DPI 越高图片越清晰。

#### `browser_extract_pdf_text`
提取指定页的结构化文本。
- **主要参数**:
  - `pdf_path` (str): 本地绝对路径或项目相对路径。
  - `pages` (list[int], 可选): 1-indexed 的页码列表。不传则默认读取全量页面文本。
