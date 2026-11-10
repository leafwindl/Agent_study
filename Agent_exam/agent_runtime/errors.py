class AgentError(Exception):
    """Agent 运行时的异常。"""


class ToolNotFoundError(AgentError):
    """找不到工具的异常。"""
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"工具 {tool_name} 未找到。")

class ToolValidationError(AgentError):
    """工具参数验证失败的异常。"""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"工具 {tool_name} 参数验证失败: {message}")

class ToolExecutionError(AgentError):
    """工具执行失败的异常。"""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"工具 {tool_name} 执行失败: {message}")

class OutputParsingError(AgentError):
    """输出解析失败的异常。"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"输出解析失败: {message}")

class MaxStepsExceededError(AgentError):
    """超过最大步骤数的异常。"""
    def __init__(self, max_steps: int):
        self.max_steps = max_steps
        super().__init__(f"超过最大步骤数: {max_steps}")

class LLMError(AgentError):
    """LLM 调用失败的异常。"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"LLM 调用失败: {message}")

class SessionError(AgentError):
    """会话异常。"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"会话异常: {message}")