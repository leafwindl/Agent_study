import os
from dotenv import load_dotenv
from openai import OpenAI
from agent_runtime.tools.registry import ToolRegistry
from agent_runtime.tool_types import ToolSpec
import json

load_dotenv()


class DeepSeekClient:
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    def _to_schemas(self, tools: list[ToolRegistry]) -> list[dict]:
        result = []
        for spec in tools:
            properties = spec.parameters
            required = list(properties.keys())
            result.append({
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return result

    def send_request(self, messages: list[dict], tools: list[ToolRegistry]) -> dict:
        """
        发送请求到 DeepSeek API。
        """
        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        response = client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=self._to_schemas(tools),
            tool_choice="auto"
        )
        return response.choices[0].message

    def completed(self, messages: list[dict], tools: list[ToolSpec]) -> dict:
        """
        调用 DeepSeek API 的 completed 接口，返回一个 dict，表示模型的回复。
        """
        
        # 发送请求到 DeepSeek API

        response = self.send_request(messages, tools)

        if response.tool_calls:
            tool_call = response.tool_calls[0]
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                raise OutputParsingError(f"工具调用参数不是有效的 JSON: {tool_call.function.arguments}") from e
            return {
                "type": "tool_call",
                "id": tool_call.id,
                "thought": getattr(response, "reasoning_content", "") or "",
                "name": tool_call.function.name,
                "args": args,
            }
        else:
            return {"type": "final", "text": response.content}

    