# Testing Notes

这个目录不是简单堆测试文件的地方，而是项目行为的回归保护层。

## 当前测试分布

- `test_cli.py`: 启动参数和运行入口
- `test_config.py`: 配置加载与校验
- `test_server.py`: 应用装配与基础能力烟雾测试
- `test_browser_config.py`: 浏览器搜索 YAML 配置与环境变量覆盖
- `test_bing_provider.py`: Bing 页面解析与广告候选识别
- `test_search_cache.py`: 临时缓存命中、过期与清理
- `test_search_results.py`: 广告过滤、去重与结果规范化
- `test_browser_service.py`: 高层搜索编排与缓存降级
- `test_browser_session.py`: 低层浏览器会话工具链

## 新测试怎么放

遵循一个简单原则：尽量让测试文件名和被测职责对得上。

例如：

- 新增 `tools/filesystem.py`，优先考虑对应的 `test_tools_filesystem.py`
- 新增 `services/weather.py`，优先考虑对应的 `test_services_weather.py`

## 编写偏好

- 优先测稳定行为，不测实现细节
- 能单元测的逻辑，不要一开始就走集成测试
- 对配置、路径、协议名这类容易静默出错的边界，保持最小覆盖

## 运行方式

```powershell
conda activate classbot-mcp
$env:VIRTUAL_ENV = $env:CONDA_PREFIX
uv run --active pytest
```

如果当前终端环境对 `pytest` 标准输出有兼容性问题，可以临时把输出重定向到文件再查看结果。
