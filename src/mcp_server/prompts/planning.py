"""规划分析及需求梳理的提示词模板定义。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def summarize_request(task: str) -> str:
    """构建用于需求梳理与执行规划的可复用系统级提示词模板。

    Args:
        task (str): 用户输入的自然语言请求或具体技术任务描述。

    Returns:
        str: 拼装好的系统级架构分析提示词模板。
    """
    return (
        "You are an expert system architect and lead developer. Please analyze the following "
        "user task with extreme detail:\n\n"
        f"TASK: {task}\n\n"
        "Your analysis MUST include:\n"
        "1. **Input Analysis**: Identify all required data points and their source.\n"
        "2. **Output Specification**: Define the exact format and content of the expected result.\n"
        "3. **Technical Constraints**: List any known limitations, security concerns, "
        "or dependencies.\n"
        "4. **Step-by-Step Execution Plan**: Provide a logical sequence of actions to "
        "fulfill the request.\n"
        "5. **Validation Strategy**: How will we know the implementation is successful?\n\n"
        "Please provide a structured response."
    )


def register_planning_prompts(mcp: FastMCP) -> None:
    """向 FastMCP 应用注册与任务规划相关的提示词模板。

    Args:
        mcp (FastMCP): 待注册提示词的 FastMCP 服务实例。
    """
    mcp.prompt(
        name="summarize_request",
        description=(
            "A high-level planning prompt to help analyze complex tasks and draft execution plans."
        ),
    )(summarize_request)
