

from agent_runtime.tool_types import ToolSpec


class MockLLMClient:
    def __init__(self, model_name: str = "mock"):
        self.model_name = model_name
        self._call_seq = 0  # 用来伪造唯一的调用 id

    def completed(self, messages: list[dict], tools: list[ToolSpec]) -> dict:
        self._call_seq += 1

        # 确定可用工具
        available = [t.name for t in tools]

        last = messages[-1]

        # 最后一条是工具结果直接返回 final
        if last["role"] == "tool":
            return {
                "type": "final",
                "text": f"工具返回的结果是：{last['content']}",
            }

        # 如果最后一条是用户消息，判断是否要调工具
        text = last.get("content") or ""

        if "weather" in available and "天气" in text:
            city = text.replace("帮我查", "").replace("的天气", "").strip()
            return {
                "type": "tool_call",
                "id": f"mock_call_{self._call_seq}",
                "thought": f"用户要查{city}的天气，应该用 weather",
                "name": "weather",
                "args": {"city": city},
            }

        if "calculator" in available and "算" in text:
            expr = text.replace("帮我算", "").replace("算", "").strip()
            return {
                "type": "tool_call",
                "id": f"mock_call_{self._call_seq}",
                "thought": f"用户要算 {expr}，应该用 calculator",
                "name": "calculator",
                "args": {"expression": expr},
            }
        if "todo_add" in available and ("记一下" in text or "添加" in text):
            item = text
            for prefix in (
                "帮我记一下：",
                "帮我记一下",
                "帮我添加一个待办事项：",
                "帮我添加一个待办事项",
            ):
                item = item.replace(prefix, "")
            item = item.strip()
            return {
                "type": "tool_call",
                "id": f"mock_call_{self._call_seq}",
                "thought": f"用户要记 {item}，应该用 todo_add",
                "name": "todo_add",
                "args": {"item": item},
            }
        if "todo_list" in available and ("待办" in text or "列出" in text):
            return {
                "type": "tool_call",
                "id": f"mock_call_{self._call_seq}",
                "thought": f"用户要查待办事项列表，应该用 todo_list",
                "name": "todo_list",
                "args": {},
            }

        # 不调工具，直接回复
        return {"type": "final", "text": "收到，我先记下了。"}
