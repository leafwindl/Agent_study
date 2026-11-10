"""
第一课：用 60 行看懂 Agent 主循环到底在干什么。

不联网、不装任何依赖、不用真模型。
运行：python playground/01_fake_loop.py

这个文件不是项目代码，是教学脚手架。看完就该删掉或者忘了它。
但它里面的循环结构，和最终项目里的主循环是一模一样的。
"""

# 设置一个Tool字典
TOOLS = {}

# 
def tool(name, description, parameters):
    """注册一个工具。最终项目里会长成 tools/registry.py，但本质就是往字典里塞。"""

    def wrapper(fn):
        TOOLS[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": fn,
        }
        return fn

    return wrapper


@tool("calculator", "计算数学表达式", {"expression": {"type": "string"}})
def calculator(expression):
    return eval(expression)  # 教学用。真实项目必须换成安全求值，后面会讲为什么


@tool("echo", "原样返回一段文字", {"text": {"type": "string"}})
def echo(text):
    return text

@tool("weather", "预测天气", {"city": {"type": "string"}})
def weather(city):
    return f"{city}的天气是：晴天"

def fake_llm(messages): # {"role": "user", "content": "帮我算 1+2*3"}
    """
    假装自己是模型。
    真实项目里这里换成一次 HTTP 请求，其余逻辑完全不变——
    这就是为什么我们要把 LLM 做成可注入接口。
    """
    # return {"type": "tool_call", "thought": None, "name": "calculator","args": {"expression": "1+2*3"}}
    last = messages[-1] # {"role": "user", "content": "帮我算 1+2*3"}

    # 看到工具结果 -> 收工，给最终答案
    if last["role"] == "tool":
        return {"type": "final", "text": f"{last['content']}"}

    text = last["content"]

    # 看到"算"字 -> 决定调工具（这就是所谓的"模型自主决策"）
    if "算" in text:  # 有算字触发
        expr = text.replace("帮我算", "").replace("算", "").strip() # 数据清洗为 "1+2*3"
        return {
            "type": "tool_call",
            "thought": f"用户要算{expr}，得用计算器", 
            "name": "calculator",
            "args": {"expression": expr}, # "1+2*3"
        }
    
    if "天气" in text:  # 有天气触发
        city = text.replace("帮我查", "").replace("的天气", "").strip() # 数据清洗为 "北京"
        return {
            "type": "tool_call",
            "thought": f"用户要查{city}的天气，得用天气工具", 
            "name": "weather",
            "args": {"city": city}, # "北京"
        }

    # 其他情况 -> 直接回复，不调工具
    return {"type": "final", "text": "收到，我先记下了。"}


def run(user_input, max_steps=5):
    messages = [{"role": "user", "content": user_input}] # {"role": "user", "content": "帮我算 1+2*3"}

    for step in range(1, max_steps + 1):
        print(f"\n--- 第 {step} 轮 ---")

        # ===== 1. 问模型 =====
        reply = fake_llm(messages) # {"type": "tool_call", "name": "calculator", "args": {"expression": "1+2*3"}}
        print(f"[llm 返回] {reply}")

        # ===== 2. 分支 A：模型说"我答完了" =====
        if reply["type"] == "final":
            messages.append({"role": "assistant", "content": reply["text"]})
            print(f"[最终 messages] {messages}")
            return reply["text"]

        # ===== 3. 分支 B：模型说"我要调工具" =====
        tool_name = reply["name"]
        tool_args = reply["args"] # {"expression": "1+2*3"}
        call_id=f"call_{step}"
        messages.append({"role": "assistant", "content": reply["thought"], "tool_calls":[{"id": call_id, "name": tool_name, "args": tool_args}]})
        print(f"[执行工具] {tool_name}({tool_args})")

        handler = TOOLS[tool_name]["handler"]
        result = handler(**tool_args)  # ** 把 dict 摊成关键字参数，字典的键当参数名，值当参数值。

        # ===== 4. 关键一步：把工具结果塞回 messages，再转一圈 =====
        messages.append({"role": "tool", "id": call_id, "name": tool_name, "content": str(result)})

    # ===== 5. 循环保护 =====
    return "超过最大轮次，我放弃了。"


if __name__ == "__main__":
    # 三个场景必须一起留着。以后每加一个功能，这三个都得还绿。
    print("=" * 50)
    print("场景 1：直接回复（不该调工具）")
    print("=" * 50)
    print("最终答案:", run("你好"))

    print("\n")
    print("=" * 50)
    print("场景 2：查询天气（调 weather）")
    print("=" * 50)
    print("最终答案:", run("帮我查北京的天气"))

    print("\n")
    print("=" * 50)
    print("场景 3：计算表达式（调 calculator）")
    print("=" * 50)
    print("最终答案:", run("帮我算 1+2*3"))