"""session 存储层测试。"""

import unittest

from agent_runtime.session.model import Session
from agent_runtime.session.store import InMemorySessionStore


class TestSessionStore(unittest.TestCase):

    def setUp(self):
        # 每个 test_ 方法开始前都会执行一次，保证测试之间互不影响
        self.store = InMemorySessionStore()

    def test_save_then_load(self):
        """存进去，能读出来。"""
        s = Session(id="w1", messages=[], todos=["买菜"], created_at=0.0, updated_at=0.0)
        self.store.save(s)

        loaded = self.store.load("w1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.todos, ["买菜"])

    def test_two_sessions_do_not_mix(self):
        """两个 session 的 todo 必须各归各的。"""
        self.store.save(Session(id="w1", messages=[], todos=["买菜"], created_at=0.0, updated_at=0.0))
        self.store.save(Session(id="w2", messages=[], todos=["吃饭"], created_at=0.0, updated_at=0.0))

        self.assertEqual(self.store.load("w1").todos, ["买菜"])
        self.assertEqual(self.store.load("w2").todos, ["吃饭"])

    def test_load_missing_returns_none(self):
        """不存在的 session 返回 None，不抛异常。"""
        self.assertIsNone(self.store.load("不存在的id"))

    def test_load_returns_copy_not_reference(self):
        """load 出来的是副本，改它不影响存储。"""
        self.store.save(Session(id="w1", messages=[], todos=["买菜"], created_at=0.0, updated_at=0.0))

        loaded = self.store.load("w1")
        loaded.todos.append("偷偷加的")        # 改副本

        again = self.store.load("w1")
        self.assertNotIn("偷偷加的", again.todos)   # 存储里不该有


if __name__ == "__main__":
    unittest.main()