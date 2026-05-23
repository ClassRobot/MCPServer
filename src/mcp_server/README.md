# Package Map

这里是项目真正的 Python 包：`mcp_server`。

如果把整个项目想成一栋楼，这个目录就是主楼层，其他同级目录只是楼外的配套设施。

## 先看哪里

第一次进入这个包，推荐按下面顺序看：

1. [`__main__.py`](__main__.py): 进程启动入口，负责命令行参数。
2. [`app.py`](app.py): `FastMCP` 应用装配点。
3. [`config.py`](config.py): 统一配置来源。
4. [`tools/`](tools/README.md): MCP tools。
5. [`resources/`](resources/README.md): MCP resources。
6. [`prompts/`](prompts/README.md): MCP prompts。

## 文件职责地图

| 文件 | 角色 | 应不应该写业务 |
| --- | --- | --- |
| `__main__.py` | CLI 启动入口 | 不应该 |
| `app.py` | 应用装配 | 不应该 |
| `config.py` | 配置读取与校验 | 只允许配置逻辑 |
| `server.py` | 对外导出稳定入口 | 不应该 |

## 包内协作规则

- 新增能力时，优先落到子目录，不要回流到 `app.py`。
- `app.py` 只做注册和装配，不做具体实现。
- 配置读取必须集中，避免在 tool 内部偷偷读环境变量。
- 当某个能力开始有自己的业务复杂度，再向下拆 `services/`、`schemas/`、`adapters/`。
- 运行和测试默认依赖已激活的 conda 环境 `classbot-mcp`，并在 PowerShell 中额外设置 `$env:VIRTUAL_ENV = $env:CONDA_PREFIX`，不要假设项目内存在 `.venv`。
