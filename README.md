# Agent 学习路径

从零手写 Agent 的各个核心组件，**不依赖 LangGraph / OpenHands / OpenClaw 等现成框架**。
每个阶段一个独立可运行的工程，包含设计文档、测试和踩坑记录。

---

## 进度

| 阶段 | 主题 | 状态 | 目录 |
|---|---|---|---|
| **01** | **Agent Loop**（工具调用、session、context、trace） | ✅ 完成 | [`Agent_exam/`](Agent_exam/) |
| 02 | Memory（长期记忆、检索式记忆） | ⬜ 待开始 | — |
| 03 | RAG（检索增强生成） | ⬜ 待开始 | — |
| 04 | Multi-Agent（协作与编排） | ⬜ 待开始 | — |
| 05 | Evaluation（Agent 评测） | ⬜ 待开始 | — |

---

## 阶段 01 · Agent Loop ✅

### 目标

实现一个最小可用但边界清晰的 Agent Runtime：
**接收用户输入 → 由 LLM 自主决定调不调工具 → 执行工具 → 结果回灌 → 继续循环或返回答案。**

### 交付物

- **主循环**：带最大轮次预算，工具异常不中断
- **5 个工具**：`calculator` / `echo` / `weather` / `todo_add` / `todo_list`
- **工具注册**：`ToolSpec(name, description, parameters, fn)` + Schema 驱动的自主调用
- **2 个 LLM 后端**：`DeepSeekClient`（OpenAI 兼容协议）与 `MockLLMClient`，同契约可互换
- **session 管理**：`Session` / `SessionStore` 协议，两个窗口互不干扰
- **context 管理**：字符预算投影 + 超限压缩（摘要置顶）
- **异常处理**：LLM 失败终止 / 工具异常回灌 / 参数校验拦截
- **结构化 trace**：可注入的 `Tracer` 协议
- **21 个单元测试**

### 核心问题速答

| 问题 | 答案 |
|---|---|
| Agent 主循环是什么？ | 一个带预算的 while：把历史发给模型，看它返回 `final` 还是 `tool_call`，后者执行工具并把结果追加回 `messages` |
| LLM 无状态，怎么“记住”之前？ | 每轮重发完整历史。所以 `messages` 长度随轮次增长就是“记住了”的可观测证据（`llm.calls == [1, 3]`） |
| 两个窗口怎么保证不串？ | `session_id` 做唯一键 + `messages`/`todos` 挂在 `Session` 上 + `SessionStore` 进出双向拷贝 |
| 工具失败要不要中断循环？ | 不要。包装成 `tool` 消息回灌，让模型自己决定重试/换工具/解释 |
| context 超长怎么办？ | 预算内投影；超限时从后往前攒，被丢弃部分压成 `system` 摘要置顶，且至少保留最后一条 |
| 怎么证明“能追问”？ | Spy 型假客户端记录每轮收到的消息数，断言它递增 |
| 为什么工具函数第一个参数是 `ctx`？ | 工具要访问运行时状态（当前 session），状态挂 session 才能隔离；`ctx` 不进 JSON Schema，LLM 看不到 |

### 目录

```
Agent_exam/
├── agent_runtime/          # 库：loop / tools / llm / session / context / trace
├── tests/                  # 21 个单元测试
├── playground/             # 60 行教学原型（理解循环的第一步）
├── docs/
│   ├── PROTOCOL.md         # 消息与事件的逐字段协议手册
│   └── LEARNING_LOG.md     # 20 个踩坑记录 + 知识点总复习
├── main.py                 # 演示入口
└── README.md               # 题目原文 + 参考答案索引 + 设计决策
```

### 运行

```bash
cd Agent_exam

# mock 模式（不花钱）
python main.py

# 真实 DeepSeek
export USE_REAL_LLM=1
export DeepSeek_API_KEY=sk-xxx
python main.py

# 测试
python -m unittest discover -s tests -t .
```

### 相关文档

| 文档 | 内容 |
|---|---|
| [Agent_exam/README.md](Agent_exam/README.md) | 题目原文、15 项要求的参考答案索引、6 条核心设计决策、8 条已知边界 |
| [Agent_exam/docs/PROTOCOL.md](Agent_exam/docs/PROTOCOL.md) | OpenAI 消息格式与内部事件格式的完整对照 |
| [Agent_exam/docs/LEARNING_LOG.md](Agent_exam/docs/LEARNING_LOG.md) | 从 60 行原型到 12 个模块的全过程，20 个坑的根因分析 |

---

## 后续计划

| 阶段 | 要解决的问题 |
|---|---|
| **Memory** | 跨 session 的长期记忆：怎么存、怎么召回、怎么避免污染 |
| **RAG** | 文档切分、向量检索、引用溯源、检索结果如何进 context |
| **Multi-Agent** | 任务分解、角色分工、消息传递、冲突收敛 |
| **Evaluation** | 如何度量 Agent 的好坏：任务成功率、工具调用正确率、成本 |

---

## 约定

- 每个阶段独立目录，可单独运行
- 每个阶段都有 README（设计）+ PROTOCOL（协议）+ LEARNING_LOG（踩坑）
- 核心组件手写，不引框架跑主流程
- API key 一律走环境变量，`.env` 永不提交
