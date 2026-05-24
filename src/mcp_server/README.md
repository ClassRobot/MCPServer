# Main Package Map

本包承载 MCP Server 的生命周期装配、入口管理以及所有的分层业务逻辑。

## 模块结构导航

1. **[`__main__.py`](__main__.py) / [`server.py`](server.py)**: CLI 启动入口与应用外部导出点。
2. **[`app.py`](app.py)**: `FastMCP` 核心实例化与子模块接口能力组装点。
3. **[`config.py`](config.py)**: 统一配置解析、环境变量加载及格式校验器。
4. **子能力模块**:
   - **[`tools/`](tools/README.md)**: 客户端可执行工具（如浏览器动作、检索等）。
   - **[`resources/`](resources/README.md)**: 供客户端读取的静态或状态元数据。
   - **[`prompts/`](prompts/README.md)**: 预设交互与业务上下文模板。
5. **底层支撑分层**:
   - **[`services/`](services/README.md)**: 核心跨 Tool 业务流程流转与结果加工过滤。
   - **[`adapters/`](adapters/README.md)**: 浏览器实例、第三方搜索源（如 Bing）与搜索缓存的生命周期管理。
   - **[`schemas/`](schemas/README.md)**: 跨层交互的强类型 Pydantic 数据结构。

## 协作开发规约

- **严禁业务混入**: 新增核心逻辑应严格落入子模块，`app.py` 仅保留 `FastMCP` 能力注册逻辑。
- **统一配置入口**: 严禁在底层模块直接读取环境变量，所有外部变量应由 `config.py` 校验后全局流转。
- **适时下沉**: 局部 Tool 逻辑出现复杂外部依赖调度、错误重试或自定义持久化时，应及时下沉解耦至 `services/` 或 `adapters/`。

