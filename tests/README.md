# Test Directory

本目录存放所有的自动化测试，作为项目稳定运行的回归保护层。

## 测试组织与分布
测试文件名与 `src/` 中的被测职责保持镜像映射：

- **系统基础与入口**:
  - `test_cli.py`: 命令行参数与启动逻辑。
  - `test_config.py`: 环境变量与配置项解析。
  - `test_server.py`: 服务端装配与基础能力冒烟测试。
- **业务编排与逻辑**:
  - `test_browser_config.py`: 浏览器配置文件与环境变量覆盖校验。
  - `test_browser_service.py`: 搜索高层流程编排与缓存降级。
  - `test_database.py`: 数据库配置、迁移与查询历史服务闭环验证。
  - `test_search_results.py`: 搜索结果重组、去重与广告过滤。
- **底层适配与缓存**:
  - `test_browser_session.py`: Playwright 浏览器生命周期与页面提取。
  - `test_search_cache.py`: 缓存命中、TTL 过期及并发清理安全性。
  - `test_bing_provider.py`: Bing 页面解析与广告候选提取。

## 编写与扩增原则
- **职责镜像**: 新增测试文件时，命名须与被测模块映射（例如新增 `src/mcp_server/tools/filesystem.py` 时，对应编写 `tests/test_tools_filesystem.py`）。
- **稳定优先**: 优先测试外部行为与核心接口，不绑定过度设计的内部实现；单元测试为主，集成测试为辅。
- **边界覆盖**: 对配置解析、类型转换及外部依赖异常等边界必须提供最小化覆盖。

## 运行测试
```bash
uv run pytest
```
