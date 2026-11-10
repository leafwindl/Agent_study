# 最小可用 Agent Runtime

## 原始任务

> **Vibe coding 题目：从零实现一个最小可用 Agent**
>
> **要求 1：从零完成**
> 不能依赖现有 agent 框架（langgraph / openhands / openclaw）完成主流程；
> 允许使用任何 AI 工具辅助开发，但核心 Agent Runtime 需要自行实现。
>
> **要求 2：实现基本循环**
>
> ```
> Step one   接收用户输入
> Step two   判断是直接回复，还是调用工具
> Step three 调用工具
> Step four  根据工具结果判断是继续 loop，还是返回结果给用户
> ```
>
> - **工具相关**：至少实现三个工具（todo 必须实现）：calculator、search（可 mock）、
>   read_docs / todo / weather（可自定义）。需实现工具注册机制（每个工具包含名称、描述、
>   参数 Schema），LLM 基于 Schema 自主决策调用。需实现 LLM 输出的解析逻辑，
>   提取思考过程、工具调用或最终答案。
> - **session 管理**：用户 A 开了窗口 1 让 Agent 查天气记待办，开了窗口 2 让 Agent 写周报记待办。
>   这两个窗口应该是独立 session，用户 A 可以随时接着窗口 1/2 继续聊，彼此不会影响。
> - **context 的有效管理**：最大轮次限制；用户持续的对话要能记住之前的状态；
>   能支持追问（纯对话追问、带工具的追问）；要如何实现？哪些信息要塞入 context 更合适？
>   （用户输入、工具执行结果、Agent 思考过程等，自行判断。）
>   context 过长要有基础的压缩，复杂的压缩不用在这里实现。
> - **额外要求**：基本异常处理；工具调用 trace 或执行日志。
>
> **要求 3：测试用例构建**
> 构建测试用例，来测试以上功能。

---

## 参考答案索引

| 题目要求 | 落点 | 实现方式 |
|---|---|---|
| 从零完成、不依赖 Agent 框架 | 全部 `agent_runtime/` | 仅依赖 `openai` + `python-dotenv`；循环、注册、解析、session、context、trace 全部手写，无 LangGraph / OpenHands / OpenClaw |
| 基本循环 4 步 | `loop/runtime.py::run` | `for step in range(1, maxsteps+1)`：投影 context → 问模型 → 判 `final`/`tool_call` → 执行工具 → 回灌 → 下一轮 |
| ≥3 个工具（todo 必须） | `tools/builtin.py` | 共 5 个：`calculator` / `echo` / `weather` / `todo_add` / `todo_list` |
| 工具注册机制（名称+描述+Schema） | `tool_types.py` + `tools/registry.py` | `ToolSpec(name, description, parameters, fn)`，`parameters` 即 JSON Schema 的 properties；`ToolRegistry` 负责注册与查找 |
| LLM 基于 Schema 自主决策 | `llm/deepseek.py::_to_schemas` | 把 `ToolSpec` 转成 OpenAI function schema，含 `{"type":"object","properties","required"}` 三层，随 `tools=` 参数发出 |
| 输出解析（思考 / 调用 / 答案） | `llm/deepseek.py::completed` | 统一译成内部事件：`{"type":"final","text"}` 或 `{"type":"tool_call","id","thought","name","args"}`；`thought` 取模型调工具前的文本 / `reasoning_content` |
| session 管理（两窗口独立） | `session/` + `run(session_id, ...)` | `Session{id, messages, todos, created_at, updated_at}`；`SessionStore` 协议 + 内存实现；todo 状态挂 `session.todos`，不挂全局 |
| 随时接着聊 | 同上 | `run()` 开头 `store.load(session_id)`，取不到才新建；`finally` 中统一 `store.save()`，所有出口都落盘 |
| 最大轮次限制 | `run(..., maxsteps=5)` | 超出返回「超过最大轮次」；测试 `test_max_steps_exceeded` |
| 纯对话追问 | `session.messages` 持续追加 | 每轮把完整历史投影后重发（LLM 无状态）。测试断言 `llm.calls == [1, 3]` |
| 带工具追问 | `tool` 消息回灌 | 工具结果以 `{"role":"tool","tool_call_id","content"}` 追加，模型据此继续决策 |
| context 长度控制与压缩 | `context/builder.py` | 字符预算 + `json.dumps` 精确计长；超限时从后往前攒，被丢弃部分压成 `system` 摘要置于最前；至少保留最后一条 |
| 基本异常处理 | `runtime.py` + `errors.py` + `ToolSpec.execute` | 三层：LLM 调用失败→终止返回；工具异常→包装成 `tool` 消息回灌不中断；参数非法→`ToolValidationError` 拦截 |
| 工具调用 trace | `trace/tracer.py` | `Tracer` 协议 + `PrintTracer` / `NoopTracer`；结构化事件 `[step]` `[llm_reply]` `[tool_call]` `[tool_error]` `[final]` |
| 测试用例 | `tests/`（21 个） | 覆盖存储、隔离、追问、工具循环、超轮次、工具异常、工具不存在、解析失败、参数校验、压缩、trace |

### 题目追问的正面回答

**Q：哪些信息要塞入 context 更合适？**

| 信息 | 是否入 context | 理由 |
|---|---|---|
| 用户输入 | ✅ 必须全留 | 意图来源，压缩时优先保留关键实体（人名、城市、事项） |
| 工具执行结果 | ✅ 以 `tool` 消息保留 | 模型必须看到结果才能回答；压缩时可摘要，但不可静默丢弃 |
| Agent 的思考（thought） | ⚠️ 写入 `assistant.content` | 有连贯性价值，但会持续占用 token；属于最先可压缩的内容 |
| 工具调用参数 | ✅ 以结构化 `tool_calls` 保留 | 回传时必须与 `tool_call_id` 配对，否则模型认不出自己的调用 |
| 早期历史 | ⚠️ 超预算时压缩为 `system` 摘要 | 保摘要丢原文，换取「还能接上追问」 |

**Q：多轮追问为什么能接上？**
LLM 是无状态的，每轮都会重发完整历史；「记住」= 「把历史完整寄过去」。因此 `messages` 长度随轮次增长是可观测证据（`llm.calls == [1, 3]`）。

**Q：两个窗口怎么保证不串？**
隔离靠三件事：`session_id` 作为唯一键、`messages` / `todos` 挂在 `Session` 上、`SessionStore` 进出双向拷贝（不共享可变对象）。

---

## 项目简介

一个从零实现的 Agent 运行时：**不依赖 LangGraph / OpenHands / OpenClaw 等任何 Agent 框架**，
核心循环、工具注册、输出解析、session / context 管理、异常处理、trace 全部手写。

支持 **DeepSeek（OpenAI 兼容协议）** 与 **Mock 两种 LLM 后端**，零框架依赖（仅 `openai` + `python-dotenv`）。

---

## 一、职责边界

> **它负责「会话状态 + 用户输入 → 模型决策 → 工具执行 → 结果回灌 → 最终回复」的控制流编排；
> 不负责模型推理本身、不负责工具的真实业务实现、不负责 HTTP 接入层与鉴权。**

一句话记住：**它是 loop，不是 model，也不是 API 层。**
凡是「决定下一步做什么」的代码在 Runtime；凡是「把话说清楚」的代码不该在 Runtime。

---

## 二、快速开始

### 环境

- Python 3.10+（开发环境 3.13）
- `pip install openai python-dotenv`

### 配置

在项目根目录建 `.env`：

```ini
DeepSeek_API_KEY=sk-xxxx
BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-chat
```

> **代码中不出现任何密钥**，全部从环境变量读取；
> `DeepSeekClient` 构造时若拿不到 key 会直接抛 `LLMError`，不会静默失败。

### 运行

```powershell
# 用 mock（不花钱，1 秒跑完所有场景）
$env:PYTHONIOENCODING='utf-8'
python main.py

# 用真实模型
$env:USE_REAL_LLM='1'
python main.py
```

### 测试

```powershell
python -m unittest discover -s tests -t .
```

```
Ran 21 tests in 0.0xx s
OK
```

---

## 三、架构

```
Agent_exam/
├── agent_runtime/
│   ├── tool_types.py        # ToolSpec（含参数校验）+ execute()
│   ├── errors.py            # 统一异常体系（AgentError 为基类）
│   ├── llm/
│   │   ├── mock.py          # MockLLMClient：按关键词模拟决策
│   │   └── deepseek.py      # DeepSeekClient：OpenAI 协议双向映射
│   ├── tools/
│   │   ├── registry.py      # 注册表：注册 / 查找 / 列举
│   │   └── builtin.py       # calculator / echo / weather / todo_add / todo_list
│   ├── session/
│   │   ├── base.py          # SessionStore 协议（Protocol）
│   │   ├── model.py         # Session 数据模型
│   │   └── store.py         # InMemorySessionStore
│   ├── context/
│   │   └── builder.py       # ContextBuilder：预算内投影 + 超限压缩
│   ├── trace/
│   │   └── tracer.py        # Tracer 协议 + PrintTracer + NoopTracer
│   └── loop/
│       └── runtime.py       # AgentRuntime：唯一编排者
├── tests/                   # 21 个测试
├── playground/              # 教学原型（60 行假循环）
├── docs/
│   ├── PROTOCOL.md          # 消息与事件格式手册
│   └── LEARNING_LOG.md      # 从零实现的过程记录与踩坑
└── main.py                  # 演示入口
```

### 模块职责

| 模块 | 职责 | 关键接口 |
|---|---|---|
| `ToolSpec` | 工具的描述 + 参数校验 + 执行 | `execute(ctx, args)` |
| `ToolRegistry` | 工具的注册与查找 | `register_tool` / `get_tool` / `list_tools` |
| `LLMClient`（两个实现） | 把「消息列表」变成「内部事件」 | `completed(messages, tools) -> dict` |
| `SessionStore` | session 的持久化边界 | `load` / `save` |
| `ContextBuilder` | 决定「这一轮发什么给模型」 | `build_context(session)` |
| `Tracer` | 结构化事件输出 | `log(kind, **fields)` |
| `AgentRuntime` | 主循环编排、异常兜底、状态落盘 | `run(session_id, user_input, maxsteps)` |

### 依赖方向

```
AgentRuntime
   ├──> ContextBuilder ──> Session（只读投影）
   ├──> LLMClient（协议注入，两个实现）
   ├──> ToolRegistry ──> ToolSpec ──> 工具函数
   ├──> SessionStore（协议注入）
   └──> Tracer（协议注入）
```

**Runtime 是唯一有状态的编排者**，其余模块都是可替换的、职责单一的实现。

---

## 四、核心设计决策

### 1. 内部 messages 直接采用 OpenAI 协议

**问题**：多一层自定义格式，就要多一层双向转换。

**选择**：`messages` 全程使用 OpenAI 的 `{role, content, tool_calls, tool_call_id}` 结构。

**理由**：目标模型就是 OpenAI 兼容协议，省掉输入侧的全部映射，只需要在**出口**（响应 → 内部事件）做一次翻译。
如果将来要多厂商支持，在 `LLMClient` 边界加 adapter 即可，Runtime 不受影响。

> 这也解释了为什么 `DeepSeekClient` 里没有 `_to_openai_messages`——不需要。

### 2. 工具的统一签名是 `(ctx, **业务参数)`

**问题**：todo 需要读写「当前会话」的状态，但工具函数只收到 LLM 给的参数。

**选择**：所有工具第一个参数固定为 `ctx`（当前实现是 `Session`），由 Runtime 注入。
**`ctx` 不写进 JSON Schema**，LLM 看不到它。

**理由**：状态必须挂在 session 上才能实现隔离。如果 todo 用模块级全局变量，两个窗口立刻串数据。
`ctx` 也是未来的扩展点（工作目录、用户 ID、超时预算等都可以挂进来）。

### 3. 工具失败是「数据」，不是「故障」

**问题**：工具抛异常了，循环该不该中断？

**选择**：不中断。把错误包装成 `tool` 消息回灌给模型，让它自己决定重试 / 换工具 / 跟用户解释。

```python
try:
    reply = self.llm_client.completed(...)
except Exception as e:
    return f"调用 LLM 接口失败: {type(e).__name__}: {e}"
```

**理由**：Runtime 中断 = 剥夺模型的纠错能力。
只有 **LLM 调用本身失败**才终止（此时没有决策者了），工具层的任何错误都应该先让模型看到。

### 4. `ContextBuilder` 只做投影，绝不修改 session

**问题**：压缩要不要把旧消息从 session 里删掉？

**选择**：不删。`build_context()` 每次返回一份「这一轮要发的消息」，`session.messages` 永远是完整真相源。

**理由**：压缩是**视图**，不是**销毁**。否则一次误判就把用户历史永久删掉了。
测试 `test_builder_does_not_modify_session` 专门守这条。

### 5. trace 是可注入的抽象

**选择**：`Tracer` 协议 + `PrintTracer` / `NoopTracer` 两个实现。

**理由**：测试时注入 `NoopTracer` 保证输出干净；生产环境可换成结构化日志或上报到观测平台，**Runtime 一行不用改**。

事件是结构化字段（`kind` + `**fields`），不是拼接字符串：

```
[step] step=1 msg_count=1
[tool_call] step=1 name=todo_add args={'item': '买菜'}
[tool_error] step=1 name=todo_add error=ToolValidationError
```

### 6. 同步实现，不引入 async

**理由**：单用户 CLI 场景没有并发需求，同步代码可读性高一个数量级。
引入 async 只会分散在「为什么这里要 await」上，掩盖真正的控制流。

> 如果要做多用户服务，并发问题应该在 SessionStore 层对 session 加锁串行化，而不是把整个 Runtime 改成异步。

---

## 五、主循环

```
load session（没有就建）
  ↓
追加 user 消息
  ↓
┌─ for step in 1..maxsteps ──────────────────────────┐
│  ContextBuilder.build_context()   ← 预算内投影/压缩 │
│       ↓                                            │
│  LLMClient.completed()            ← 失败则终止      │
│       ↓                                            │
│  是 final？  ──是──> 返回答案，落盘                  │
│       │否                                           │
│       ↓                                            │
│  是 tool_call？                                    │
│       ↓                                            │
│  ToolSpec.execute()               ← 校验+执行       │
│       ↓                                            │
│  结果/错误写入 tool 消息，继续循环                    │
└────────────────────────────────────────────────────┘
  ↓
超过 maxsteps → 返回「超过最大轮次」
  ↓
finally: 保存 session（所有出口都覆盖）
```

**存储保存在 `finally` 里**，保证无论从哪条路径退出（正常返回、超限、异常），session 都会被落盘。

---

## 六、测试覆盖

| 测试文件 | 覆盖内容 | 数量 |
|---|---|---|
| `test_sessions.py` | 存储读写、引用隔离、缺失返回 None | 4 |
| `test_runtime.py` | 主循环、工具调用、长历史、会话隔离、参数校验、异常兜底、trace | 13 |
| `test_context.py` | 预算内直通、超限截断、关键实体保留、不修改 session | 4 |

几个关键的断言：

```python
# 追问时历史被带上：第 2 轮收到 3 条消息（user + assistant + user）
self.assertEqual(llm.calls, [1, 3])

# 两个 session 不串
self.assertNotIn("买菜", self.store.load("s2").todos)

# 压缩后关键实体还在
self.assertIn("小明", result[0]["content"])

# 工具异常不崩，循环活到第 2 轮
self.assertEqual(answer, "我换个方式")
```

> **测试技巧**：用 `Spy` 型假客户端记录每轮收到的消息条数，把「历史有没有被带上」这种不可见的行为变成可断言的数字。

---

## 七、已知边界（刻意不做/暂不实现）

| 边界 | 说明 | 如果要做 |
|---|---|---|
| **多工具并行** | 只处理 `tool_calls[0]`，一次只执行一个 | 遍历全部调用，按 id 一一回填 |
| **压缩粒度** | 只保留 user 消息的关键实体，工具结果不进摘要 | 按重要性采样，或改用 LLM 摘要 |
| **摘要缓存** | 每次超预算都重新生成，未写回 session | session 增加 `summary` 字段并失效更新 |
| **持久化** | `InMemorySessionStore`，重启即失忆 | 换 `FileSessionStore`（JSON），接口已抽象好 |
| **并发** | 单线程 CLI，未处理同一 session 并发调用 | SessionStore 层加锁串行化 |
| **calculator 安全性** | 使用 `eval`，生产环境危险 | 换 `ast.literal_eval` 或受限求值器 |
| **token 估算** | 字符数粗估，非精确 tokenizer | 换 `tiktoken` 或厂商 count_tokens |
| **多模态** | 不支持图片/音频消息 | 与本题无关 |

**主动列出边界而不是假装完美**——面试官一定会问「有什么不足」，提前答完就是加分项。

---

## 八、演进记录

```
playground/01_fake_loop.py（60 行假循环，无框架无依赖）
        ↓ 拆工程 / 类型契约 / 依赖注入
agent_runtime/（12 个模块，5 个工具，2 个 LLM 后端，21 个测试）
```

中间踩过的坑、每个设计的原因，记录在 [`docs/LEARNING_LOG.md`](docs/LEARNING_LOG.md)。
消息与事件的完整字段说明见 [`docs/PROTOCOL.md`](docs/PROTOCOL.md)。
