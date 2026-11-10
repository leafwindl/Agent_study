import unittest

from agent_runtime.loop.runtime import AgentRuntime
from agent_runtime.session.store import InMemorySessionStore
from agent_runtime.tool_types import ToolSpec
from agent_runtime.tools.registry import ToolRegistry
from agent_runtime.tools.builtin import todo_add, todo_list
from agent_runtime.context.builder import ContextBuilder
from agent_runtime.session.model import Session


class TestContext(unittest.TestCase):

    def setUp(self):
        self.context_builder = ContextBuilder(max_chars=100)


    def test_small_session_passes_through(self):
        """小 session 直接通过，不会被截断，直接测试 ContextBuilder.build_context 的行为."""
        session = Session(
            id="test",
            messages=[
                {"role": "user", "content": "消息1"},
                {"role": "user", "content": "消息2"}
            ],
            todos=[],
            created_at=0.0,
            updated_at=0.0
        )
        context = self.context_builder.build_context(session)
        self.assertEqual(len(context), 2)
        self.assertEqual(context[0]["role"], "user")
        self.assertEqual(context[0]["content"], "消息1")
        self.assertEqual(context[1]["role"], "user")
        self.assertEqual(context[1]["content"], "消息2")


    def test_large_session_truncates(self):
        """大 session 会被截断，保证传给模型的消息数量不超过预算."""
        session = Session(
            id="test",
            messages=[
                {"role": "user", "content": "消息1"},
                {"role": "user", "content": "消息2"},
                {"role": "user", "content": "消息3"},
                {"role": "user", "content": "消息4"},
                {"role": "user", "content": "消息5"},
                {"role": "user", "content": "消息6"},
            ],
            todos=[],
            created_at=0.0,
            updated_at=0.0
        )
        context = self.context_builder.build_context(session)
        self.assertEqual(len(context), 3)  
        self.assertEqual(context[0]["content"], "此前用户提到：消息1；消息2；消息3；消息4")
        self.assertEqual(context[1]["content"], "消息5")
        self.assertEqual(context[2]["content"], "消息6")

    def test_builder_does_not_modify_session(self):
        """ContextBuilder.build_context 不会修改 session。"""
        session = Session(
            id="test",
            messages=[
                {"role": "user", "content": "消息1"},
                {"role": "user", "content": "消息2"},
                {"role": "user", "content": "消息3"},
                {"role": "user", "content": "消息4"},
                {"role": "user", "content": "消息5"},
                {"role": "user", "content": "消息6"},
            ],
            todos=[],
            created_at=0.0,
            updated_at=0.0
        )
        original_messages = session.messages.copy()
        _ = self.context_builder.build_context(session)
        self.assertEqual(session.messages, original_messages)

    def test_compressed_context_includes_summary(self):
        """当消息被截断时，压缩后的 context 包含摘要信息。"""
        session = Session(
            id="test",
            messages=[
                {"role": "user", "content": "消息1"},
                {"role": "user", "content": "消息2"},
                {"role": "user", "content": "消息3"},
                {"role": "user", "content": "消息4"},
                {"role": "user", "content": "消息5"},
                {"role": "user", "content": "消息6"},
            ],
            todos=[],
            created_at=0.0,
            updated_at=0.0
        )
        context = self.context_builder.build_context(session)
        self.assertEqual(context[0]["role"], "system") 
        self.assertTrue(any("此前用户提到" in msg.get("content", "") for msg in context))
    