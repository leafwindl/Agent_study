from dataclasses import dataclass, field
from agent_runtime.tool_types import ToolSpec
from agent_runtime.errors import ToolNotFoundError

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, ToolSpec] = {}

    def register_tool(self, tool_spec: ToolSpec):
        """注册一个工具"""
        if self.tools is None:
            self.tools = {}
        self.tools[tool_spec.name] = tool_spec
    
    def get_tool_names(self) -> list[str]:
        """返回所有工具的名称"""
        return list(self.tools.keys())
    
    def get_tool(self, tool_name: str) -> ToolSpec:
        """根据工具名称返回工具的 ToolSpec"""
        if self.tools is None or tool_name not in self.tools:
            raise ToolNotFoundError(tool_name)
        return self.tools[tool_name]

    def schemas(self) -> dict[str, dict]:
        """返回所有工具的 JSON Schema"""
        return {name: tool_spec.parameters for name, tool_spec in self.tools.items()}

    def get_tool_parameters(self, tool_name:str) -> dict[str, dict]:
        """根据工具名称返回工具的 JSON Schema"""
        if self.tools is None or tool_name not in self.tools:
            raise ToolNotFoundError(tool_name)
        return self.tools[tool_name].parameters
    
    def list_tools(self) -> list[ToolSpec]:
        """返回所有工具的列表，每个工具包含 name, description, parameters"""
        return list(self.tools.values())

        

