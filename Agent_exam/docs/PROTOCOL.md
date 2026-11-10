# Agent Runtime 接口协议手册

> **一句话记住**：`messages` 用 **OpenAI 协议**（因为要发给真实模型），
> `completed()` 的返回值用 **我们自己的内部事件协议**（因为只有 runtime 读它）。
> 两者不是同一个东西，格式不同是正常的。

---

## 0. 三层概念

```
┌─────────────────────────────────────────────────────────┐
│ ① messages        发出去的对话历史  →  OpenAI 协议       │
│                    全链路统一，存进 session 的就是它      │
├─────────────────────────────────────────────────────────┤
│ ② 模型原始响应     DeepSeek 返回的对象                   │
│                    resp.choices[0].message               │
├─────────────────────────────────────────────────────────┤
│ ③ 内部事件        {"type": "final" | "tool_call", ...}   │
│                    client 把 ② 翻译成 ③，交给 runtime     │
└─────────────────────────────────────────────────────────┘
```

`completed()` 的契约：**输入 ①，输出 ③**。

---

## 1. 发送侧：messages 的四种角色

只有 `assistant` 有两种形态，其他三种固定。

### 1.1 `user` —— 用户输入

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `role` | `str` | ✅ | 固定 `"user"` | `"user"` |
| `content` | `str` | ✅ | 用户说的话 | `"帮我查北京的天气"` |

```python
{"role": "user", "content": "帮我查北京的天气"}
```

---

### 1.2 `assistant`（纯文本）—— 模型把话说完了

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `role` | `str` | ✅ | 固定 `"assistant"` | `"assistant"` |
| `content` | `str` | ✅ | 模型说的话 | `"北京目前是晴天 ☀️"` |

```python
{"role": "assistant", "content": "北京目前是晴天 ☀️"}
```

---

### 1.3 `assistant`（调用工具）—— 唯一复杂的形态

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `role` | `str` | ✅ | 固定 `"assistant"` |
| `content` | `str \| None` | ✅ | 模型顺带说的话（thought），可以是 `None` |
| `tool_calls` | `list` | ✅ | 要调用的工具列表 |

`tool_calls` 每个元素：

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `id` | `str` | ✅ | 本次调用的回执号，模型给的，**原样保留** | `"call_00_ET_EkoY..."` |
| `type` | `str` | ✅ | 固定 `"function"` | `"function"` |
| `function.name` | `str` | ✅ | 工具名 | `"weather"` |
| `function.arguments` | `str` | ✅ | 参数，**JSON 字符串**，不是 dict | `'{"city": "北京"}'` |

```python
{
    "role": "assistant",
    "content": "用户要查北京的天气，应该用 weather",
    "tool_calls": [{
        "id": "call_00_ET_EkoYOrO1v2GzSsQDE0PT9243",
        "type": "function",
        "function": {
            "name": "weather",
            "arguments": "{\"city\": \"北京\"}"
        }
    }]
}
```

> ⚠️ 三个必踩的坑：漏 `type`、漏 `function` 这层包装、把 `arguments` 写成 dict。

---

### 1.4 `tool` —— 工具执行结果

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `role` | `str` | ✅ | 固定 `"tool"` | `"tool"` |
| `tool_call_id` | `str` | ✅ | **必须**等于上面 `tool_calls[].id` | `"call_00_ET_EkoY..."` |
| `content` | `str` | ✅ | 工具返回结果（字符串化） | `"北京的天气是：晴天"` |

```python
{
    "role": "tool",
    "tool_call_id": "call_00_ET_EkoYOrO1v2GzSsQDE0PT9243",
    "content": "北京的天气是：晴天"
}
```

> ⚠️ `tool_call_id` 写错 = 模型认不出这是它的调用结果，会答非所问。
> ⚠️ 注意字段名是 `tool_call_id`，**不是** `id`。

---

### 发送侧字段速查

| role | 必填字段 | 可选/额外 |
|---|---|---|
| `user` | `role`, `content` | — |
| `assistant`（文本） | `role`, `content` | — |
| `assistant`（调工具） | `role`, `content`, `tool_calls` | — |
| `tool` | `role`, `tool_call_id`, `content` | — |

---

## 2. 接收侧：DeepSeek 返回什么

### 2.1 完整层级

```python
ChatCompletion(
    id="...",
    model="deepseek-chat",
    object="chat.completion",
    created=1799999999,
    usage=CompletionUsage(
        prompt_tokens=348,          # 输入 token 数（M4 压缩要用）
        completion_tokens=25,       # 输出 token 数
        total_tokens=373,
    ),
    choices=[
        Choice(
            index=0,
            finish_reason="tool_calls",     # ← 关键：判断模型想干什么
            message=ChatCompletionMessage(  # ← 真正要的，下一节展开
                ...
            ),
        )
    ],
)
```

> 你的 `send_request()` 返回的已经是 `response.choices[0].message`，
> 所以你能直接 `response.content` / `response.tool_calls`。

---

### 2.2 形态 A：模型决定调用工具

```python
ChatCompletionMessage(
    role="assistant",
    content="",                      # 通常空字符串，也可能是 None
    tool_calls=[
        ChatCompletionMessageFunctionToolCall(
            id="call_00_ET_EkoYOrO1v2GzSsQDE0PT9243",
            type="function",
            function=Function(
                name="weather",
                arguments='{"city": "北京"}',    # ★ 字符串，要 json.loads
            ),
        )
    ],
    reasoning_content="",            # DeepSeek 扩展字段
    refusal=None,
    annotations=None,
    audio=None,
    function_call=None,              # 旧 API 遗留，忽略
)
```

**读取方式：**

```python
if msg.tool_calls:
    tc = msg.tool_calls[0]
    tool_name = tc.function.name
    tool_args = json.loads(tc.function.arguments)
    call_id = tc.id
```

---

### 2.3 形态 B：模型给出最终答案

```python
ChatCompletionMessage(
    role="assistant",
    content="北京目前是**晴天** ☀️\n\n需要我帮你查别的城市吗？",
    tool_calls=None,
    reasoning_content="",
    ...
)
```

**读取方式：**

```python
if not msg.tool_calls:
    return {"type": "final", "text": msg.content}
```

---

### 2.4 `finish_reason` 的取值

| 值 | 含义 | 你要做什么 |
|---|---|---|
| `stop` | 正常说完 | 返回最终答案 |
| `tool_calls` | 模型要调工具 | 执行工具后继续循环 |
| `length` | 撞到 max_tokens 被截断 | 当前未处理，应视为异常 |

---

### 2.5 `reasoning_content` 说明

- 这是 **DeepSeek 扩展字段**，不是 OpenAI 标准字段
- 本次测试中部分请求返回了内容（模型的内部思考，常常是英文）
- 用 `getattr(msg, "reasoning_content", "")` 读取最安全
- 它会进 messages 的 `content`，**会占用 context**

---

### 2.6 可以完全忽略的字段

| 字段 | 为什么不用管 |
|---|---|
| `refusal` | 拒答标记，本题不涉及 |
| `annotations` | 引用标注，不涉及 |
| `audio` | 语音输出，不涉及 |
| `function_call` | 旧版 function calling 遗留 |
| `tool_calls[].type` / `index` | 固定值 / 顺序索引 |

---

## 3. 内部事件契约

### 3.1 方法签名

```python
def completed(self, messages: list[dict], tools: list[ToolSpec]) -> dict:
```

| 参数 | 类型 | 说明 |
|---|---|---|
| `messages` | `list[dict]` | OpenAI 协议格式的消息列表 |
| `tools` | `list[ToolSpec]` | 可用工具列表（**不是** ToolRegistry） |

> 命名建议：方法名用动词原形 `complete` 更规范；当前代码为 `completed`，后续可统一。

---

### 3.2 只能返回两种形状

**① 最终答案**

```python
{"type": "final", "text": "北京目前是晴天 ☀️"}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `str` | 固定 `"final"` |
| `text` | `str` | 给用户的最终回答 |

**② 要调工具**

```python
{
    "type": "tool_call",
    "id": "call_00_ET_EkoYOrO1v2GzSsQDE0PT9243",
    "thought": "用户要查北京的天气，应该用 weather",
    "name": "weather",
    "args": {"city": "北京"},
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `str` | 固定 `"tool_call"` |
| `id` | `str` | 调用回执号，**真模型必须原样回传**；mock 可自造 |
| `thought` | `str \| None` | 模型的思考/说明，可为空 |
| `name` | `str` | 工具名 |
| `args` | `dict` | 参数，**已解析成 dict**（不是字符串） |

> ⚠️ 注意区别：消息里 `arguments` 是 **字符串**，事件里 `args` 是 **dict**。
> client 负责 `json.loads`，runtime 拿到的就是 dict。

---

### 3.3 两个实现必须返回同一形状

| | MockLLMClient | DeepSeekClient |
|---|---|---|
| `type` | `"tool_call"` | `"tool_call"` |
| `id` | `"mock_call_2"` | `"call_00_ET_..."` |
| `thought` | 中文说明 | 模型的 reasoning |
| `name` | `"weather"` | `"weather"` |
| `args` | `{"city": "北京"}` | `{"city": "北京"}` |

**除此之外只有 id 格式不同——所以 runtime 一行不用改。**

**验收标准：把 `MockLLMClient()` 换成 `DeepSeekClient(...)`，`runtime.py` 不改还能跑。**

---

## 4. 一次完整交互，messages 怎么长出来

```
【开始】
  [ {user} ]

【第 1 轮】调模型 → 模型说"要调 weather"
  追加 assistant(tool_calls)：
  [ {user}, {assistant, tool_calls} ]

【执行工具】拿到 "北京的天气是：晴天"
  追加 tool：
  [ {user}, {assistant, tool_calls}, {tool} ]

【第 2 轮】调模型 → 模型基于结果给出答案
  追加 assistant(content)：
  [ {user}, {assistant, tool_calls}, {tool}, {assistant, content} ]

【结束】返回最后的 content
```

**每一轮的完整 messages 都会重新发给 API** —— LLM 没有记忆，
它看到的是你这次寄过去的全部历史。

---

## 5. 发送 ↔ 接收 对照速查

| 你做的事 | 发送什么 | 从哪读结果 |
|---|---|---|
| 用户说话 | `{"role":"user","content":...}` | — |
| 调模型 | 整个 messages + tools | `resp.choices[0].message` |
| 判断意图 | — | `msg.tool_calls` 是否为 None |
| 取工具名 | — | `msg.tool_calls[0].function.name` |
| 取参数 | — | `json.loads(msg.tool_calls[0].function.arguments)` |
| 取回执号 | — | `msg.tool_calls[0].id` |
| 取模型文本 | — | `msg.content` |
| 取思考过程 | — | `msg.reasoning_content`（可有可无） |
| 回填调用记录 | `{"role":"assistant","tool_calls":[...]}` | — |
| 回填工具结果 | `{"role":"tool","tool_call_id":...,"content":...}` | — |

---

## 6. 常见错误对照表

| 症状 | 原因 | 修复 |
|---|---|---|
| 第二次请求 400 | messages 里有非法消息 | 检查 assistant 的 `tool_calls` 结构 |
| 模型说"我不知道你在说什么" | `tool_call_id` 和 `tool_calls[].id` 不一致 | 用模型给的 id，别自己编 |
| 模型不调工具 | 没给 API 传 `tools` 参数 | `create(..., tools=...)` |
| 参数类型错 | `arguments` 直接塞了 dict | `json.dumps(args)` |
| `NameError: ToolSpec` | 用了类型注解但没 import | `from agent_runtime.tool_types import ToolSpec` |
| 模型答非所问 | tool 消息里没有 `content` | 补上结果字符串 |

---

## 7. 当前代码对照

| 文件 | 负责哪一段 |
|---|---|
| `agent_runtime/tool_types.py` | `ToolSpec` 定义（name / description / parameters / fn） |
| `agent_runtime/tools/registry.py` | 工具注册表，`list_tools()` 返回 `list[ToolSpec]` |
| `agent_runtime/llm/deepseek.py` | ①→DeepSeek，②→③ 的翻译 |
| `agent_runtime/llm/mock.py` | 假模型，同样输出 ③ |
| `agent_runtime/loop/runtime.py` | 组装 ①、读 ③、驱动循环 |
