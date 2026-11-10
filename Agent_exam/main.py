"""
演示入口。

运行前：
    $env:DeepSeek_API_KEY = "sk-..."
    $env:USE_REAL_LLM = "1"        # 不设则用 mock，不花钱

    $env:PYTHONIOENCODING = "utf-8"
    python main.py
"""

import os

from dotenv import load_dotenv

from agent_runtime.context.builder import ContextBuilder
from agent_runtime.llm.deepseek import DeepSeekClient
from agent_runtime.llm.mock import MockLLMClient
from agent_runtime.loop.runtime import AgentRuntime
from agent_runtime.session.store import InMemorySessionStore
from agent_runtime.tool_types import ToolSpec
from agent_runtime.tools.builtin import calculator, echo, weather, todo_add, todo_list
from agent_runtime.tools.registry import ToolRegistry
from agent_runtime.trace.tracer import PrintTracer

load_dotenv()


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_tool(
        ToolSpec("calculator", "计算数学表达式", {"expression": {"type": "string"}}, calculator)
    )
    registry.register_tool(
        ToolSpec("echo", "原样返回一段文字", {"text": {"type": "string"}}, echo)
    )
    registry.register_tool(
        ToolSpec("weather", "查询城市天气", {"city": {"type": "string"}}, weather)
    )
    registry.register_tool(
        ToolSpec("todo_add", "添加一条待办事项", {"item": {"type": "string"}}, todo_add)
    )
    registry.register_tool(
        ToolSpec("todo_list", "列出所有待办事项", {}, todo_list)
    )
    return registry


def build_runtime(store: InMemorySessionStore, registry: ToolRegistry) -> AgentRuntime:
    if os.getenv("USE_REAL_LLM") == "1":
        llm = DeepSeekClient(
            api_key=os.getenv("DeepSeek_API_KEY"),
            base_url=os.getenv("BASE_URL", "https://api.deepseek.com"),
            model_name=os.getenv("MODEL_NAME", "deepseek-chat"),
        )
        print(">>> 使用真实模型:", llm.model_name)
    else:
        llm = MockLLMClient()
        print(">>> 使用 mock 模型（设置 USE_REAL_LLM=1 切换真模型）")

    return AgentRuntime(
        llm,
        registry,
        store,
        context_builder=ContextBuilder(max_chars=6000),
        tracer=PrintTracer(),
    )


def show(title: str, answer: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    print(answer)


def main() -> None:
    registry = build_registry()
    store = InMemorySessionStore()
    runtime = build_runtime(store, registry)

    # 场景 1：模型直接回答，不调工具
    show("场景 1｜直接回复", runtime.run("window-1", "你好"))

    # 场景 2：模型自主决定调工具，把结果回灌后再回答
    show("场景 2｜调用工具（天气）", runtime.run("window-1", "帮我查北京的天气"))

    # 场景 3：同一窗口继续聊，历史被带上
    show("场景 3｜同窗口追问", runtime.run("window-1", "帮我查上海的天气"))

    # 场景 4：todo 状态挂在 session 上
    show("场景 4｜窗口 1 记待办", runtime.run("window-1", "帮我记一下：买牛奶"))
    show("场景 5｜窗口 1 看待办", runtime.run("window-1", "我的待办有哪些"))

    show("场景 6｜窗口 2 记待办", runtime.run("window-2", "帮我记一下：写周报"))
    show("场景 7｜窗口 2 看待办", runtime.run("window-2", "我的待办有哪些"))

    # 场景 8：窗口 1 的待办不该被窗口 2 影响
    show("场景 8｜窗口 1 再看待办（应仍只有买牛奶）", runtime.run("window-1", "我的待办有哪些"))

    # 说明：超轮次保护由 tests/test_runtime.py::test_max_steps_exceeded 覆盖。
    # mock 模型第一轮就返回 final，无法在此演示“一直调工具直到超限”。

    print("\n全部场景执行完毕。")


if __name__ == "__main__":
    main()
