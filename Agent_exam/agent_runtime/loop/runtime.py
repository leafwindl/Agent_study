from agent_runtime.llm.mock import MockLLMClient
from agent_runtime.llm.deepseek import DeepSeekClient
from agent_runtime.tool_types import ToolSpec
from agent_runtime.tools.registry import ToolRegistry
from agent_runtime.session.base import SessionStore
from agent_runtime.session.model import Session
from agent_runtime.context.builder import ContextBuilder
from agent_runtime.trace.tracer import NoopTracer

import time

import json

class AgentRuntime:
    def __init__(self, llm_client: MockLLMClient, registry: ToolRegistry, store: SessionStore, context_builder = None, tracer = None):
        self.llm_client = llm_client
        self.tool_registry = registry
        self.store = store
        self.context_builder = ContextBuilder()
        self.tracer = tracer or NoopTracer()

    def run(self, session_id: str, user_input: str, maxsteps = 5) -> str:
        session = self.store.load(session_id)
        if session is None:
            session = Session(
                id=session_id,
                messages=[],
                todos=[],
                created_at=time.time(),
                updated_at=time.time()
            )
        session.messages.append({"role": "user", "content": user_input})

        try:
            for step in range(1, maxsteps + 1):
                send_messages = self.context_builder.build_context(session)
                # 记录每轮的消息条数，方便调试和分析
                self.tracer.log("step", step=step, msg_count=len(send_messages))  

                try:
                    reply = self.llm_client.completed(send_messages, self.tool_registry.list_tools())
                except Exception as e:
                    # 记录 LLM 调用失败的错误信息
                    self.tracer.log("llm_error", step=step, error=type(e).__name__)
                    return f"调用 LLM 接口失败: {type(e).__name__}: {e}"

                # 记录 LLM 回复的类型和内容（前 40 个字符），方便调试和分析
                self.tracer.log("llm_reply", step=step, type=reply["type"]) 
                
                if reply["type"] == "final":
                    # 记录最终回复的内容（前 40 个字符），方便调试和分析
                    self.tracer.log("final", step=step, text=reply["text"][:40]) 
                    session.messages.append({"role": "assistant", "content": reply["text"]})
                    return reply["text"]

                tool_name = reply["name"]
                tool_args = reply["args"]
                call_id = reply.get("id", f"call_{step}")
                session.messages.append({
                    "role": "assistant", 
                    "content": reply.get("thought", ""), 
                    "tool_calls":[{
                        "id": call_id, 
                        "type": "function",
                        "function": {
                            "name": tool_name, 
                            "arguments": json.dumps(tool_args, ensure_ascii=False)
                        }
                    }],
                })

                # 记录工具调用的名称和参数，方便调试和分析
                self.tracer.log("tool_call", step=step, name=tool_name, args=tool_args) 

                try:
                    handler = self.tool_registry.get_tool(tool_name)
                    result = handler.execute(session, tool_args)
                    content = str(result)
                    # 记录工具执行成功的结果，方便调试和分析
                    self.tracer.log("tool_ok", step=step, name=tool_name)
                except Exception as e:
                    content = f"工具执行失败: {type(e).__name__}: {e}"
                    self.tracer.log("tool_error", step=step, name=tool_name,error=type(e).__name__)
                session.messages.append({"role": "tool", "tool_call_id": call_id, "content": content})

            return "超过最大轮次，我放弃了。"
        finally:
            session.updated_at = time.time()
            self.store.save(session)