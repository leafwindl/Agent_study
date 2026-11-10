"""runtime 主循环测试。"""

import unittest
import io

from agent_runtime.loop.runtime import AgentRuntime
from agent_runtime.session.store import InMemorySessionStore
from agent_runtime.tool_types import ToolSpec
from agent_runtime.tools.registry import ToolRegistry
from agent_runtime.tools.builtin import todo_add, todo_list, calculator, echo
from agent_runtime.session.model import Session
from agent_runtime.errors import ToolValidationError
from contextlib import redirect_stdout
from agent_runtime.trace.tracer import PrintTracer



class ScriptedLLM:
    """按剧本依次返回响应，并记录每轮收到的消息条数。"""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def completed(self, messages, tools):
        self.calls.append(len(messages))
        return self.replies.pop(0)


class TestRuntime(unittest.TestCase):

    def setUp(self):
        self.store = InMemorySessionStore()
        self.registry = ToolRegistry()
        self.registry.register_tool(
            ToolSpec("todo_add", "添加待办", {"item": {"type": "string"}}, todo_add)
        )
        self.registry.register_tool(
            ToolSpec("todo_list", "列出待办", {}, todo_list)
        )

    # ---------------- 样板 ----------------
    def test_direct_answer(self):
        """模型直接给答案，run 应该返回它，并且只调一次模型。"""
        llm = ScriptedLLM([{"type": "final", "text": "你好呀"}])
        runtime = AgentRuntime(llm, self.registry, self.store)

        answer = runtime.run("w1", "你好")

        self.assertEqual(answer, "你好呀")
        self.assertEqual(llm.calls, [1])            # 只调了一次，收到 1 条消息
        self.assertEqual(self.store.load("w1").messages[-1]["role"], "assistant")

    def test_tool_call_loop(self):
        """模型先调工具，工具返回结果后，模型再给最终答案。"""
        llm = ScriptedLLM([
            {"type": "tool_call", "id": "c1" , "thought": "我需要添加一个待办事项", "name": "todo_add", "args": {"item": "买菜"}},
            {"type": "final", "text": "完成任务"},
        ])
        runtime = AgentRuntime(llm, self.registry, self.store)

        answer = runtime.run("w1", "帮我添加一个待办事项：买菜")

        self.assertEqual(answer, "完成任务")
        self.assertEqual(llm.calls, [1, 3])         # 第 1 轮收到 1 条消息，第 2 轮收到 3 条消息
        self.assertEqual(self.store.load("w1").todos, ["买菜"])

    def test_followup_carries_history(self):
        """同一个 session 的后续调用，应该带上之前的消息历史。"""
        llm = ScriptedLLM([
            {"type": "final", "text": "我已经帮你记下了，第一次调用"},
            {"type": "final", "text": "我已经帮你记下了，第二次调用"},
        ])
        runtime = AgentRuntime(llm, self.registry, self.store)

        runtime.run("w1", "你好啊")
        runtime.run("w1", "你好啊，我又来了")

        self.assertEqual(llm.calls, [1, 3])         # 第 1 轮收到 1 条消息，第 2 轮收到 3 条消息

    def test_two_sessions_isolated(self):
        """两个 session 的消息历史应该互不干扰。"""
        llm = ScriptedLLM([
            {"type": "final", "text": "session1 第一次调用"},
            {"type": "final", "text": "session2 第一次调用"},
            {"type": "final", "text": "session1 第二次调用"},
        ])
        runtime = AgentRuntime(llm, self.registry, self.store)

        runtime.run("s1", "你好啊")
        runtime.run("s2", "你好啊")
        runtime.run("s1", "你好啊，我又来了")

        self.assertEqual(llm.calls, [1, 1, 3])      # s1 第 1 轮收到 1 条消息，s2 第 1 轮收到 1 条消息，s1 第 2 轮收到 3 条消息
        self.assertNotIn("买菜", self.store.load("s2").todos)

    def test_missing_arg_raises(self):
        spec = ToolSpec("todo_add", "添加待办", {"item": {"type": "string"}}, todo_add)
        session = self.store.load("w1") or Session(id="w1", messages=[], todos=[], created_at=0, updated_at=0)

        with self.assertRaises(ToolValidationError):
            spec.execute(session, {})            # 没给 item

    def test_unknown_arg_raises(self):
        spec = ToolSpec("calculator", "算数", {"expression": {"type": "string"}}, calculator)
        session = self.store.load("w1") or Session(id="w1", messages=[], todos=[], created_at=0, updated_at=0)

        with self.assertRaises(ToolValidationError):
            spec.execute(session, {"expression": "1+1", "多余的": 1})

    def test_valid_args_runs(self):
        spec = ToolSpec("calculator", "算数", {"expression": {"type": "string"}}, calculator)
        session = self.store.load("w1") or Session(id="w1", messages=[], todos=[], created_at=0, updated_at=0)

        self.assertEqual(spec.execute(session, {"expression": "1+2*3"}), 7)
    
    def test_unknown_tool_does_not_crash(self):
        """模型要求调一个不存在的工具，run 不应该崩。"""
        llm = ScriptedLLM([
            {"type": "tool_call", "id": "c1", "name": "不存在的工具", "args": {}},
            {"type": "final", "text": "好的，我换个方式"},
        ])
        runtime = AgentRuntime(llm, self.registry, self.store)

        answer = runtime.run("w1", "随便试试")

        self.assertEqual(answer, "好的，我换个方式")     # 循环活到了第 2 轮
        tool_msg = [m for m in self.store.load("w1").messages if m["role"] == "tool"][0]
        self.assertIn("ToolNotFoundError", tool_msg["content"])

    def test_max_steps_exceeded(self):
        """模型一直要求调工具，超过 maxsteps 后，run 应该返回错误信息。"""
        llm = ScriptedLLM([
            {"type": "tool_call", "id": "c1", "name": "todo_add", "args": {"item": "买菜"}},
            {"type": "tool_call", "id": "c2", "name": "todo_add", "args": {"item": "买水果"}},
            {"type": "tool_call", "id": "c3", "name": "todo_add", "args": {"item": "买零食"}},
            {"type": "tool_call", "id": "c4", "name": "todo_add", "args": {"item": "买饮料"}},
        ])
        runtime = AgentRuntime(llm, self.registry, self.store)

        answer = runtime.run("w1", "帮我添加一些待办事项", maxsteps=3)

        self.assertIn("超过最大轮次", answer)

    def test_tool_exception_does_not_crash(self):
        """工具执行时抛异常，run 不应该崩。"""
        def broken_tool(ctx, args):
            raise ValueError("工具内部错误")

        self.registry.register_tool(
            ToolSpec("broken", "坏掉的工具", {}, broken_tool)
        )

        llm = ScriptedLLM([
            {"type": "tool_call", "id": "c1", "name": "broken", "args": {}},
            {"type": "final", "text": "我换个方式"},
        ])
        runtime = AgentRuntime(llm, self.registry, self.store)

        answer = runtime.run("w1", "试试坏掉的工具")

        self.assertEqual(answer, "我换个方式")     # 循环活到了第 2 轮
        tool_msg = [m for m in self.store.load("w1").messages if m["role"] == "tool"][0]
        self.assertIn("工具执行失败", tool_msg["content"])

    def test_invalid_json_arguments(self):
        """模型返回的工具调用参数不是有效的 JSON，run 不应该崩。"""
        llm = ScriptedLLM([
            {"type": "tool_call", "id": "c1", "name": "todo_add", "args": "{invalid_json}"},
            {"type": "final", "text": "我换个方式"},
        ])
        runtime = AgentRuntime(llm, self.registry, self.store)

        answer = runtime.run("w1", "试试无效的 JSON 参数")

        self.assertEqual(answer, "我换个方式")     # 循环活到了第 2 轮
        tool_msg = [m for m in self.store.load("w1").messages if m["role"] == "tool"][0]
        self.assertIn("ToolValidationError", tool_msg["content"])

    def test_llm_parse_error_does_not_crash(self):
        """LLM 解析失败时，run 返回错误文本而不是崩溃。"""
        from agent_runtime.errors import OutputParsingError

        class BrokenLLM:
            def completed(self, messages, tools):
                raise OutputParsingError("模拟 JSON 解析失败")

        runtime = AgentRuntime(BrokenLLM(), self.registry, self.store)

        answer = runtime.run("w1", "随便问问")

        self.assertIn("调用 LLM 接口失败", answer)      # 不抛异常，返回友好文本

    def test_trace_emits_events(self):
        """trace 应该记录到工具调用事件。"""
        buf = io.StringIO()
        llm = ScriptedLLM([
            {"type": "tool_call", "id": "c1", "name": "todo_add", "args": {"item": "买菜"}},
            {"type": "final", "text": "完成任务"},
        ])
        with redirect_stdout(buf):
            runtime = AgentRuntime(llm, self.registry, self.store, tracer=PrintTracer())
            runtime.run("w1", "记一下买菜")

        self.assertIn("tool_call", buf.getvalue())