# 从零实现 Agent Runtime：学习日志

> 记录从 60 行假循环到 12 个模块的完整过程。
> 重点不是「写了什么」，而是**每个坑为什么踩、怎么出来的、记住什么**。

---

## Day 1 · 先搞懂「循环」到底是什么

### 做了什么

不看任何框架文档，先写了一个 60 行的 `playground/01_fake_loop.py`：

- 两个工具（calculator / weather）注册进一个 dict
- 一个 `fake_llm()` 假装模型，按关键词决定调不调工具
- `run()` 里 while 循环：问模型 → 分支 → 执行工具 → 结果塞回 messages → 再问

**这一步的价值**：在还不懂工程结构的时候，先用最短的代码建立「Agent = 一个带预算的循环」的心智模型。

### 坑 1：用自然语言记录工具调用

第一版是这样记的：

```python
content = f"我要调 calculator工具 {tool_name}，参数 {tool_args}"
messages.append({"role": "assistant", "content": content})
```

**现象**：能跑，但把工具名写死了，而且输出成 `"我要调 calculator工具 calculator"`。

**根因**：把「结构化数据」塞进了「给人读的字符串」。

**正确做法**：`content` 和 `tool_calls` 是**并列的两个字段**，不是一个字符串的两截。

```python
{
    "role": "assistant",
    "content": "用户要查北京的天气",       # 模型说的话
    "tool_calls": [{                      # 结构化字段
        "id": "call_1",
        "type": "function",
        "function": {"name": "weather", "arguments": "{\"city\": \"北京\"}"}
    }]
}
```

**记住**：`messages` 是给程序处理的数据结构，不是给模型念的台词。

### 坑 2：把 id 拼进字符串

第二次改成了：

```python
content = f"我要调用工具 {tool_name},call_{step}，参数 {tool_args}"
```

**为什么错**：如果工具返回的正文里刚好有 `(call_1)` 字样，就无法区分「哪个是 id、哪个是结果」。

**正确做法**：id 是字段，不是文本。

```python
messages.append({"role": "tool", "tool_call_id": "call_1", "content": "7"})
```

**记住**：**元数据（谁调的）和数据（结果是什么）必须分开放。**

### 坑 3：改默认值，误伤所有调用方

做「`maxsteps=1` 会怎样」实验时，直接把 `def run(user_input, max_steps=5)` 的默认值改成了 1。

**现象**：天气和计算场景全被截断了。

**正确做法**：只对那一次调用传参 `run("帮我算 1+2*3", maxsteps=1)`。

**记住**：**改默认值 = 改所有调用方的行为。**
这和「加 weather 就删掉老场景」是同一类问题：**改动的影响面不受控**。

### 坑 4：只用轮次上限挡不住死循环

构造一个永远返回 `tool_call` 的假模型，观察 5 轮全在重复 `calculator(1+2*3)`。

**发现**：轮次上限是**兜底**，不是**根治**。

真实系统还要有两道防线：

| 招式 | 做法 |
|---|---|
| 重复调用检测 | 相同 `(name, args)` 连续出现 2 次 → 警告/中断 |
| 结果重申 | 把「这个工具你已经调过，结果是 X」重新强调给模型 |

### 这一天学到的

1. **Agent 主循环 = 一个带预算的 while**：问模型 → 看它返回什么 → 要么收工，要么执行工具再回灌。
2. **messages 是结构化事件流**，不是聊天记录。
3. **id 是调用和结果之间的唯一凭证**，不靠顺序配对。
4. **加功能不能删老用例**——三个场景必须一直绿。

---

## Day 2 · 拆工程 + 接真模型

### 做了什么

- 把 60 行拆成 `types / tools / llm / loop / session / context / trace`
- 接入 DeepSeek（OpenAI 兼容协议）
- 用依赖注入让 mock 和真模型可以互换

### 坑 5：`import` 成功 ≠ 代码能跑

拆完包后从项目根目录 import：

```
ModuleNotFoundError: No module named 'agent_runtime'
```

**根因**：`python xxx.py` 时，`sys.path[0]` 是**脚本所在目录**，不是当前目录。

| 运行方式 | `sys.path[0]` |
|---|---|
| `python `tests/test_x.py`` | `tests/` |
| `python -m unittest tests.test_x` | **当前工作目录** |

**记住**：包内代码一律写全路径 `from agent_runtime.xxx import`，入口和测试都放包外、从根目录跑。

### 坑 6：批量替换误伤标准库

把 `from tool_types import ...` 批量改成 `from agent_runtime.tool_types import ...` 时，
`from dataclasses import dataclass` 也被改成了 `from agent_runtime.dataclasses import ...`。

**报错**：`ModuleNotFoundError: No module named 'agent_runtime.dataclasses'`

**记住**：**批量替换前先看影响范围。** 标准库永远不带包名前缀。

### 坑 7：client 建好了，但没传 tools

真模型接上后，问“1+2*3”，模型老老实实心算，从不调工具。

**根因**：`client.chat.completions.create(model=..., messages=...)` **漏了 `tools` 参数**。

模型根本不知道系统里有哪些工具，当然不会调。

**记住**：**工具调用能力由 `tools` 参数提供，不是靠 prompt 里写「你可以用计算器」骗出来的。**

### 坑 8：以为要自己拼 prompt

第一次写 `DeepSeekClient` 时，写成了：

```python
def _format_messages(self, messages, tools) -> str:   # ← 返回 str 就错了
def send_request(self, prompt: str):
    requests.post(f"{base_url}/v1/llm", ...)          # ← 这个端点不存在
```

**根因**：凭想象编 API，而不是先看 SDK 签名。

**记住**：**写 API 调用前先看官方文档/SDK 签名。** 这 40 分钟本来可以省掉。

### 坑 9：第二次请求 400

**关键认知**：

> **LLM 是无状态的。每一次 `create()` 调用，你都在把整本对话记录重新寄一遍。**

- 第一次成功：`messages` 里只有一条合法的 `user`
- 第二次失败：`messages` 里多了自己拼的 `assistant(tool_calls)`，格式不合法 → 整个请求被拒

**服务端校验的是整个 messages 列表，不是最后一条。**

这直接解释了后来为什么需要 session、需要上下文压缩。

### 坑 10：id 必须原样回传

mock 时代可以自己造 `call_1`。真模型必须用模型给的：

```python
call_id = reply.get("id") or f"call_{step}"
```

因为下一轮把 `tool` 消息发回去时，`tool_call_id` 必须和 `assistant.tool_calls[].id` **完全一致**。

用自己编的 id，模型会认不出这是它刚才的调用，你会得到「我不知道你在说什么」，而且极难查。

### 这一天学到的

1. **输入格式 ≠ 输出格式**是接口设计的常态（`complete(messages) -> event`）。
2. **`tools` 是独立参数**，工具调用能力来自协议，不来自 prompt。
3. **每次调用都重发完整历史**——这是后面所有 context 设计的前提。
4. **可注入接口**的价值：mock 和真模型返回同形状的事件，Runtime 一行不用改。

---

## Day 4 · Session 与隔离

### 做了什么

- `Session` 数据模型（messages + todos + 时间戳）
- `SessionStore` 协议 + `InMemorySessionStore`
- `run(session_id, user_input)` 签名
- todo 工具（状态挂 session）
- 两个窗口互不干扰的演示

### 坑 11：漏了最关键的字段

第一版 `Session` 只有 `id / todos / created_at / updated_at`——**没有 `messages`**。

而这正是 M3 的全部意义：把对话历史从局部变量搬进 session。

**记住**：动手前先问自己「这一步的核心目标是什么」，别照着清单填字段。

### 坑 12：返回值是引用，不是副本

```python
return Session(todos=session_data["todos"], ...)     # 同一个 list
```

**后果**：

```python
s = store.load("a")
s.todos.append("买牛奶")      # 没调 save
store.load("a").todos          # 已经有"买牛奶"了
```

存储被外部偷偷改了，`updated_at` 却没更新——状态不一致。

**记住**：

> `int/str/float/tuple` 不可变，赋值安全；
> **`list/dict/set` 可变，赋值 = 共享引用。**

**进也拷、出也拷**：存储层和调用方之间永远不共享可变对象。

### 坑 13：`try` 没包住所有外部输入

```python
handler = self.tool_registry.get_tool(tool_name)     # ← 在 try 外面
try:
    result = handler.execute(...)
except Exception:
    ...
```

模型要求调不存在的工具时，`get_tool` 抛 `ToolNotFoundError`，**没人接，整个 run 崩掉**。

**记住**：**`try` 应该包住「所有来自外部的、可能不可靠的东西」。**
模型给的 `tool_name` 和 `tool_args` 都是外部的，从查表那一刻起就该在保护范围内。

### 坑 14：删了类，没删引用

删掉 `ToolResult` / `RunResult` 后，`registry.py` 里还留着：

```python
from agent_runtime.tool_types import ToolSpec, ToolResult, RunResult
```

结果两个测试模块都 `ImportError`，而报错只指向「导入失败」，看不出是谁删的。

**记住**：**删一个类之前，先 grep 一遍它的名字（或 IDE 的 find references）。**

### 关于 todo 的隔离

```python
TODOS = []                    # ❌ 全局变量 → 两个窗口立刻串
def todo_add(ctx, item):
    ctx.todos.append(item)    # ✅ 状态挂 session → 天然隔离
```

**这就是为什么工具需要 `ctx`**：工具要访问运行时状态，但状态必须属于 session，不属于进程。

### 这一天学到的

1. **状态存哪里，决定了隔离能不能成立。**
2. **引用 vs 副本**是 Python 最容易忽略的细节，也是数据污染的主要来源。
3. **Protocol 是结构化的**：不继承也满足，价值在「沟通意图」和 IDE 提示。
4. 改动前先跑回归，绿了再往下走。

---

## Day 6 · Context 管理、异常与 trace

### 做了什么

- `ContextBuilder`：预算内直通 / 超限截断 / 摘要压缩
- `ToolSpec.execute()`：参数校验
- 工具异常回灌（不中断循环）
- `Tracer` 协议 + `PrintTracer` / `NoopTracer`
- 测试从 4 个涨到 21 个

### 坑 15：测试绿 ≠ 行为对

`ContextBuilder` 第一版：

```python
for message in reversed(session.messages[-self.recent:]):   # ← 先切片
```

**结果**：永远最多发 5 条，`max_chars=6000` 从没生效过。

**但测试全绿**——因为测试断言的就是「发 5 条」，代码确实这么做了。

> **测试通过只能证明「代码符合你的预期」，不能证明「代码符合需求」。**

**记住**：写测试前先回答「这个功能的**正确行为**是什么」，而不是「我的代码现在做了什么」。

### 坑 16：估算只算了 content

```python
message_length = len(f"{message['role']}: {message['content']}")
```

带 `tool_calls` 的 assistant 消息 `content` 是空字符串 → 被算成 0 字符，实际有 150+。

**后果**：以为没超预算，实际超了，压缩永远不触发，直到 API 400。

**改法**：

```python
message_length = len(json.dumps(message, ensure_ascii=False))
```

### 坑 17：压缩可能返回空列表

```python
for message in reversed(...):
    if total_chars + message_length > self.max_chars:
        break          # 第一条就 break → context = []
```

**后果**：`messages` 为空 → API 400。

**改法**：`and total_chars > 0`，保证至少保留最后一条。

### 坑 18：`json.loads` 没保护

模型返回的 `arguments` 是字符串，理论上该是合法 JSON，但真实系统里偶发脏数据。

`json.loads` 直接抛 `JSONDecodeError`，整个进程崩。

**记住**：**所有来自外部的数据，在第一次使用前就要有保护。**

### 坑 19：print 被 redirect_stdout 吃掉了

测试里写了 `tracer=PrintTracer()` 却「没打印」——

**其实是被 `with redirect_stdout(buf):` 重定向进内存了**，这是故意的。

```python
buf = io.StringIO()
with redirect_stdout(buf):
    runtime.run(...)
self.assertIn("tool_call", buf.getvalue())     # 断言「有没有打」
```

**调试口诀**：「print 没出现」先分清三种情况——
① 根本没执行到；② 输出去别处了（redirect / 管道 / buffer）；③ 被别的输出淹了。

### 坑 20：trace 不该是散落的 print

散落的 `print` 有三个问题：

1. 测试输出被淹
2. 格式不统一，机器处理不了
3. 关不掉

**正确形态**：可注入的 `Tracer` 协议。

```python
self.tracer = tracer or NoopTracer()          # 默认静默
self.tracer.log("tool_call", step=step, name=tool_name)

# 测试里：注入 NoopTracer → 输出干净
# 生产里：换成结构化日志 → Runtime 一行不用改
```

**面试话术**：「trace 是可注入的抽象，默认打 stdout，测试注入 NoopTracer，生产可换观测平台实现。」

### 这一天学到的

1. **测试是对需求的编码**，不是对现状的复述。
2. **可观测性和业务逻辑一样要有接口。**
3. **所有外部数据都要有边界保护**：LLM 参数、工具返回值、用户输入。

---

## 总复习：这些概念再想一遍

| 概念 | 一句话 |
|---|---|
| Agent 主循环 | 带预算的 while：模型决策 → 工具执行 → 结果回灌 |
| messages | 结构化事件流，不是聊天文本 |
| 无状态 LLM | 每轮都必须重发完整历史 |
| `tool_call_id` | 调用与结果的唯一凭证，必须原样回传 |
| session 隔离 | 状态挂 session，不挂进程 |
| 引用 vs 副本 | 可变对象进出存储都要拷 |
| 异常分层 | LLM 失败=终止；工具失败=数据回灌 |
| context 压缩 | 视图，不是销毁；保留关键实体 |
| 可注入 | LLM / Store / Tracer 全部走协议 |
| 测试 | Spy 记录入参，把不可见行为变成断言 |

---

## 如果重来一次，会怎么改

1. **第一天就写测试**——不只是「跑一遍看输出」。有了断言，后面每次改动都有回归保护。
2. **先定 `LLMClient` 协议再写实现**，而不是写完 mock 再迁就它改签名。
3. **trace 从第一天就做成可注入的**，省掉无数次「关不掉 print」的麻烦。
4. **估算一律用 `json.dumps` 的长度**，不要手写字段拼接。
