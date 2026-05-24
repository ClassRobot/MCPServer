# Services Guide

本目录管理跨多个 MCP 工具共享的核心业务逻辑与流程编排（Services）。

## 核心定位与原则
- **协议解耦**: 服务层代码应为纯粹的业务逻辑与流程实现，严禁使用任何 `FastMCP` 装饰器或直接处理 CLI 参数，以确保最高的可复用性与单测友好性。
- **配置集中**: 保持内部依赖的简洁性，外部配置或路径由调用方在实例化时注入。
- **当前核心职责**: 搜索总流程编排（含降级处理）、网页搜索结果去重过滤、广告屏蔽规则、数据库读写的业务归口（如查询历史记录）、数据图表配置与渲染、本地 PDF 多模态文档解析等。

---

## 核心服务组件说明

### 1. 数据库验证服务 (`query_history.py`)
- **职责**: 负责清洗 `query` / `provider` / `source_tool` 等输入。
- **机制**: 在 service 内确定事务边界，而不是让 Tool 自己拼 session。把 ORM 结果转换为 `schemas/` 下的稳定结构，避免 MCP 输出直接泄露持久化细节。

### 2. 视觉图片与数据图表渲染服务 (`rendering.py` / `ContentRenderingService`)
- **职责**: 将 HTML/Markdown 或结构化 JSON 数据转化成高对比度、极其精美的高清图片。
- **ECharts 动态图表**:
  - 内置了极具高级质感的 Light/Dark 渐变调色板与拟物阴影。
  - **无动画快照机制**: 自动在渲染模板中配置并禁用 ECharts 的初始动画 (`animation: false`)，从而使得 Playwright 可以在 DOM 载入的第一时间截取到绝对静止、清晰的图表快照，彻底消除了渲染动态残影及不必要的等待开销。
  - 支持将通用的 categories/series 数据结构自动转换成标准图表配置，并支持完全定制的 ECharts 原生 option。

### 3. 多模态 PDF 阅读服务 (`pdf_reader.py` / `PDFReadingService`) [NEW]
- **职责**: 实现本地 PDF 文件的高清渲染与结构化文本提取。
- **设计特色**:
  - **零 Poppler 二进制依赖**: 摒弃传统的 `poppler`/`pdf2image` 二进制方案，改用纯 Python 的 Google PDFium 极速绑定包 **`pypdfium2`**（自带各平台预编译二进制，体积轻量且绝对跨平台稳定）和 **`pypdf`**。
  - **非阻塞式多线程解耦**: 将 CPU 密集型的 PDFium 光栅化像素点阵渲染和文本字节解析操作全部委派给 Python 的非阻塞式线程池 (`asyncio.to_thread`) 执行，确保了高并发请求下 MCP 服务异步主循环的顺畅运转。
  - **高保真光栅化**: 提供了可调节的 DPI 分辨率缩放渲染，输出的 PNG 字节码与 Base64 编码数据完美融合。
