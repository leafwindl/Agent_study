from dataclasses import dataclass
from typing import Callable, Any

from agent_runtime.errors import ToolValidationError

@dataclass # 帮忙写了构造函数
class ToolSpec:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., Any]  # 工具的处理函数

    def execute(self, ctx, args: dict):
        # 检查参数是否符合定义
        for key in args:
            if key not in self.parameters:
                raise ToolValidationError(self.name, f"未知参数 {key}")
        
        # 检查是否缺少必需参数
        for key in self.parameters:
            if key not in args:
                raise ToolValidationError(self.name, f"缺少必需参数 {key}")
            
        return self.fn(ctx, **args)