# Adapters Guide

本目录负责对接并封装项目外部的第三方库及外部系统依赖（Adapters），使高层业务保持技术中立。

## 核心定位与原则
- **技术隔离**: 集中处理第三方库（如 Playwright、Aiofiles）的接口适配、生命周期控制及外部异常转换。
- **无业务逻辑**: 仅作为纯粹的数据管道或资源执行者，不做高层流程控制，也不负责最终业务数据的过滤与格式决策。
- **当前核心职责**: 底层 Playwright 浏览器会话管理、文件系统缓存管理、搜索引擎（如 Bing）的 HTML 页面适配，以及数据库 engine / session / repository 接口封装。

## 当前数据库相关文件

- `database.py`: 统一管理 SQLAlchemy async engine、session factory 与连接初始化。
- `database_models.py`: 定义数据库 ORM 模型与命名约定。
- `query_history_repository.py`: 承接查询历史的最小持久化读写。

这些文件只负责“怎么和数据库交互”，不决定“什么时候写、写什么业务规则、写给哪个 Tool”。
