# 第一阶段：Agent Harness（智能体运行框架）

## 一、为什么学完设计模式后，下一步是 Harness

你已经掌握的 Agentic Design Patterns（智能体设计模式），解决的是：

> **一个 Agent 应该采用什么行为模式完成任务。**

例如：

- Routing（路由）决定交给谁；
- Planning（规划）决定先做什么、后做什么；
- Tool Use（工具使用）决定怎样调用外部能力；
- Reflection（反思）决定怎样检查和改进结果；
- Guardrails（安全护栏）决定哪些行为允许执行。

但这些模式本身并没有完整解决：

- Agent 从哪里启动；
- 一次任务如何形成独立的运行实例；
- 状态放在哪里；
- 模型、工具和子 Agent 如何统一调度；
- 怎样限制循环次数、Token 和执行时间；
- 中间事件如何发送给前端；
- 失败后怎样记录现场；
- 最终结果和生成文件怎样返回。

这些“把 Agent 真正运行起来”的公共设施，就是 Agent Harness。

可以先记住这一句话：

> **设计模式决定 Agent 怎么思考和协作，Harness 决定这些能力怎样被组织、约束和运行。**

---

# 二、什么是 Agent Harness

Agent Harness 目前并不是一个具有绝对统一定义的行业标准术语。

在较新的工程语境中，它通常指：

> 一套有明确工程约定、内置常用能力、负责装配和驱动 Agent 的运行框架。

LangChain 官方文档将 Agent Harness 描述为一种“带完整配套能力、具有明确设计倾向的框架”，通常内置规划、子 Agent 委派、文件系统和上下文管理等能力；它建立在更底层的 Agent Runtime（智能体运行时）之上。citeturn995372view0

典型 Harness 会把以下内容组合在一起：

```text
Model
+ Instructions
+ Context
+ Memory
+ Tools
+ Agent Loop
+ Subagents
+ Guardrails
+ Workspace
+ Events
+ Tracing
+ Budgets
+ Result
```

最终形成一个完整的运行容器：

```text
用户任务
   ↓
Agent Harness
   ├── 创建 Run
   ├── 准备上下文
   ├── 调用模型
   ├── 解析模型行为
   ├── 执行工具
   ├── 调度子 Agent
   ├── 更新状态
   ├── 检查预算和安全策略
   ├── 记录事件与 Trace
   └── 返回最终结果
```

OpenAI Agents SDK（OpenAI 智能体开发工具包）提供的内置 Agent Loop（智能体循环），就会自动完成模型调用、工具执行、工具结果回传和继续推理，直到任务完成；同时还集成了 Handoff（任务移交）、Guardrails、Session（会话状态）、Human-in-the-loop（人在回路）和 Tracing（链路追踪）。citeturn995372view1

---

# 三、Agent、Workflow、Framework、Harness、Runtime 的区别

这是面试中很容易混淆的一组概念。

| 概念                  | 主要职责                                             | LocalAgent 中的对应物                   |
| --------------------- | ---------------------------------------------------- | --------------------------------------- |
| Agent（智能体）       | 某个具备指令、模型和工具的执行角色                   | `code_expert`、`data_analyst`           |
| Workflow（工作流）    | 某类任务的具体执行流程                               | Router → RAG → Reflection → Answer      |
| Framework（开发框架） | 提供模型、工具、Agent 等开发抽象                     | LangChain、OpenAI Agents SDK            |
| Harness（运行框架）   | 把 Agent、工具、上下文、循环、策略等装配成可运行系统 | LocalAgent 目前分散在各模块中的编排代码 |
| Runtime（运行时）     | 提供持久化、恢复、调度、并发、任务队列等底层执行能力 | 目前 LocalAgent 尚未形成独立 Runtime 层 |

最重要的区别是 Harness 与 Runtime。

## 1. Harness 更关注“怎样运行 Agent”

包括：

- Agent 配置结构；
- Agent Loop；
- 工具注册与调用；
- 上下文构建；
- 子 Agent 委派；
- 安全策略；
- 生命周期钩子；
- 运行结果结构。

## 2. Runtime 更关注“怎样可靠地执行这次运行”

包括：

- Checkpoint（检查点）；
- 中断恢复；
- 长任务执行；
- 并发调度；
- 任务队列；
- 分布式 Worker（工作进程）；
- 状态持久化；
- 重试和故障恢复。

LangGraph 官方将 Runtime 的核心能力描述为持久化、长时间运行、人在回路、状态管理和低层编排控制。citeturn995372view0turn995372view2

可以使用一个类比：

```text
Agent          = 驾驶员
Workflow       = 行驶路线
Harness        = 汽车驾驶系统
Runtime        = 发动机、底盘和道路运行基础设施
```

但要注意，这些边界并不绝对。某些开发套件可能同时承担 Framework、Harness 和部分 Runtime 的职责。

---

# 四、Agent Harness 的核心组成

## 1. Agent Specification（智能体规格）

Agent 不应只是一个普通 Python 函数。

一个生产级 Agent 至少应声明：

```python
AgentSpec(
    name="code_expert",
    description="负责 Python 代码分析与审查",
    instructions="...",
    model_profile="balanced",
    tools=["read_file", "run_python"],
    skills=["python_review"],
    allowed_handoffs=["core_router"],
    max_steps=10,
)
```

它描述的是：

> 这个 Agent 是谁、能做什么、能使用哪些资源、受到什么限制。

你目前的 LocalAgent 已经有不同 Agent，但这些配置很可能分散在 Prompt、Router、工具注册和业务代码中。

Harness 的第一项任务，就是把它们统一为 `AgentSpec`。

---

## 2. Run（运行实例）

用户发送一次任务，不应该仅仅对应一次接口调用，而应该形成一个独立的 Run。

例如：

```text
run_id: run_20260712_001
thread_id: conversation_123
user_id: user_456
entry_agent: core_router
status: running
current_step: 4
max_steps: 20
```

需要区分：

- `thread_id`：一段持续对话；
- `run_id`：这次具体执行；
- `step_id`：一次模型、工具或子 Agent 操作；
- `trace_id`：整条可观测链路。

例如：

```text
Thread
 ├── Run 1
 │    ├── Step 1: Router
 │    ├── Step 2: RAG
 │    └── Step 3: Answer
 │
 └── Run 2
      ├── Step 1: Router
      ├── Step 2: Tool Call
      └── Step 3: Answer
```

没有这个层次，后面的评估、故障分析和断点恢复都会非常困难。

---

## 3. RunContext（运行上下文）

`RunContext` 保存本次执行需要依赖、但不一定由 Agent 修改的运行环境，例如：

```python
@dataclass
class RunContext:
    run_id: str
    thread_id: str
    user_id: str | None

    model_client: ModelClient
    tool_registry: ToolRegistry
    memory_store: MemoryStore
    event_bus: EventBus

    workspace_path: Path
    metadata: dict[str, Any]
```

它主要保存：

- 模型客户端；
- 工具注册表；
- Memory Store（记忆存储）；
- 用户和权限信息；
- 当前工作目录；
- 事件发送器；
- Trace 信息；
- 环境配置。

可以把它理解为：

> Agent 执行时所依赖的基础设施集合。

---

## 4. RunState（运行状态）

`RunState` 表示本次任务执行到了哪里。

```python
@dataclass
class RunState:
    status: str
    current_agent: str

    messages: list
    plan: list
    completed_steps: list

    tool_results: list
    artifacts: list
    errors: list

    step_count: int
    token_usage: int
```

需要特别区分：

```text
RunContext = 执行依赖
RunState   = 执行过程中不断变化的数据
```

例如：

- `model_client` 属于 Context；
- 当前执行到计划第几步属于 State；
- `tool_registry` 属于 Context；
- 某次工具执行结果属于 State。

这是一个常见面试问题。

---

## 5. Agent Loop（智能体循环）

Agent Harness 最核心的部分，是 Agent Loop。

简化后的循环如下：

```python
while not state.finished:
    context_data = build_context(state)

    model_output = call_model(
        agent=current_agent,
        context=context_data,
    )

    action = parse_model_output(model_output)

    if action.type == "tool_call":
        result = execute_tool(action)
        state.messages.append(result)

    elif action.type == "handoff":
        state.current_agent = action.target_agent

    elif action.type == "final_answer":
        state.final_output = action.content
        state.finished = True

    check_limits(state)
    emit_events(state)
```

真正的生产级循环还需要处理：

- 模型超时；
- 模型输出格式错误；
- 工具参数校验失败；
- 工具权限检查；
- 工具重试；
- 子 Agent 调用；
- 用户审批；
- Token 预算；
- 最大步数；
- 重复调用检测；
- 中断与取消；
- 最终输出校验。

设计模式中的 Planning、Reflection、Tool Use 和 Multi-Agent Collaboration，都运行在这个循环内部。

---

## 6. Tool Registry（工具注册表）

生产级 Harness 不应该在各个 Agent 内直接维护工具函数列表，而应提供统一的 Tool Registry。

```text
ToolRegistry
 ├── register(tool)
 ├── find(tool_name)
 ├── validate_arguments()
 ├── check_permission()
 ├── execute()
 └── record_result()
```

每个工具至少要包含：

```python
ToolSpec(
    name="write_excel",
    description="修改 Excel 文件",
    input_schema=...,
    risk_level="medium",
    timeout_seconds=60,
    requires_approval=False,
    allowed_agents=["data_analyst"],
)
```

因此 Harness 不只是“找到函数并调用”，而是：

```text
模型生成 Tool Call
        ↓
工具是否存在
        ↓
参数是否合法
        ↓
当前 Agent 是否有权限
        ↓
是否需要用户批准
        ↓
是否允许访问目标路径
        ↓
执行并捕获异常
        ↓
标准化工具结果
        ↓
写入 State 和 Trace
```

---

## 7. Context Manager（上下文管理器）

Harness 不能把数据库中的全部消息直接塞给模型。

它需要根据当前任务动态构建上下文：

```text
System Instructions
+ Agent Instructions
+ Current Task
+ Recent Messages
+ Relevant Memory
+ Retrieved Knowledge
+ Current Plan
+ Tool Results
+ Workspace Summary
```

Context Manager 需要决定：

- 哪些历史消息保留；
- 哪些历史消息压缩；
- 哪些长期记忆召回；
- 哪些 RAG 文档加入；
- 大型工具结果是否截断；
- 子 Agent 应获得多少父 Agent 上下文。

你现有的滚动摘要、SQLite FTS5（全文检索）、Chroma 向量检索都属于上下文来源，但现在还需要一个统一的 Context Manager 把它们组织起来。

---

## 8. Lifecycle Hooks（生命周期钩子）

Harness 应允许在关键节点执行公共逻辑：

```text
before_run
after_run

before_agent
after_agent

before_model
after_model

before_tool
after_tool

before_handoff
after_handoff

on_error
on_cancel
```

例如：

```python
async def before_tool(ctx, tool_call):
    await ctx.event_bus.emit(
        event_type="tool.started",
        data={
            "tool_name": tool_call.name,
            "arguments": tool_call.arguments,
        },
    )
```

生命周期钩子的价值是：

- 业务执行逻辑不必关心日志；
- 工具不必自己发送前端事件；
- 每个 Agent 不必重复统计耗时；
- 评估数据可以统一收集；
- 权限检查可以统一插入。

---

## 9. Event Bus（事件总线）

你目前已经有 `[[ORCH]]` 事件，这是 LocalAgent 向 Harness 演进时非常好的基础。

但后续最好从文本标记升级为结构化事件：

```json
{
  "event_id": "evt_001",
  "run_id": "run_001",
  "trace_id": "trace_001",
  "event_type": "tool.started",
  "agent_name": "data_analyst",
  "step_id": "step_004",
  "timestamp": "2026-07-12T10:00:00Z",
  "data": {
    "tool_name": "analyze_excel"
  }
}
```

事件类型可以统一为：

```text
run.started
run.completed
run.failed

agent.started
agent.completed
agent.handoff

model.started
model.completed

tool.started
tool.completed
tool.failed

plan.created
plan.step_started
plan.step_completed

guardrail.blocked
approval.requested
artifact.created
```

OpenAI Agents SDK 的 Tracing 会记录模型生成、工具调用、Handoff、Guardrail 和自定义事件，并使用 Trace 和 Span（跨度）表达整条执行链。citeturn995372view3

你的 `[[ORCH]]` 可以看成 Trace Event（链路事件）的初级版本。

---

## 10. Budget and Termination（预算与终止控制）

Harness 必须防止 Agent 无限运行。

至少需要以下限制：

```python
RunBudget(
    max_steps=20,
    max_model_calls=10,
    max_tool_calls=15,
    max_tokens=50_000,
    max_duration_seconds=300,
    max_retries_per_step=2,
)
```

常见终止条件包括：

```text
模型返回最终答案
达到最大步骤数
超过执行时间
超过 Token 预算
工具连续失败
重复执行相同行为
用户主动取消
Guardrail 阻止继续执行
等待人工审批
```

大厂面试中，如果只讲“让模型自己判断什么时候结束”，通常是不够的。

生产系统必须有确定性的外部限制。

---

# 五、Agent Harness 的完整生命周期

一次典型运行可以拆成以下阶段：

```text
1. Accept
   接收用户任务

2. Initialize
   创建 run_id、RunContext、RunState

3. Prepare
   加载 Agent、工具、记忆、Skill、工作区

4. Execute
   进入 Agent Loop

5. Observe
   记录事件、Trace、Token、耗时和错误

6. Control
   检查预算、安全策略、权限和审批

7. Finalize
   生成结构化最终结果

8. Persist
   保存运行记录、消息、Artifact 和评估数据

9. Return
   通过流式接口或普通接口返回前端
```

对应的状态机可以设计为：

```text
CREATED
   ↓
PREPARING
   ↓
RUNNING
   ├── WAITING_FOR_TOOL
   ├── WAITING_FOR_AGENT
   ├── WAITING_FOR_APPROVAL
   ├── PAUSED
   └── CANCELLING
   ↓
COMPLETED / FAILED / CANCELLED
```

Human-in-the-loop 场景不能简单阻塞接口。运行状态需要能够序列化，在用户批准或拒绝以后继续执行。OpenAI Agents SDK 的相关机制也是把等待审批表示为运行中断，再通过保存的 `RunState` 恢复原始运行。citeturn995372view4

这部分再往下发展，就会进入后续 Agent Runtime 和 Durable Execution（持久执行）模块。

---

# 六、你的 LocalAgent 目前处于什么阶段

严格来说，你的 LocalAgent 已经具备一个“早期自研 Harness”，只是它还没有被抽象成独立层。

## 已经具备的能力

| Harness 能力 | LocalAgent 当前基础                                          |
| ------------ | ------------------------------------------------------------ |
| Agent 定义   | `core_router`、`data_analyst`、`code_expert`、`knowledge_expert` |
| Agent 编排   | Router 拆解和委派                                            |
| 模型访问     | 本地 llama.cpp 与远程 API                                    |
| 工具系统     | 文件、Excel、CSV、系统工具                                   |
| Memory       | SQLite、滚动摘要、FTS5                                       |
| RAG          | Chroma、Embedding、文档切片                                  |
| Event        | `[[ORCH]]` 事件                                              |
| API          | FastAPI 流式聊天接口                                         |
| UI           | PyQt6 桌面端                                                 |
| 模型档位     | fast、balanced、deep                                         |

## 当前主要缺口

### 1. 缺少统一的运行对象

目前可能是：

```text
HTTP Request
→ Router
→ Agent
→ Tool
→ Response
```

后续应当成为：

```text
HTTP Request
→ HarnessRunner.create_run()
→ RunContext
→ RunState
→ Agent Loop
→ RunResult
```

### 2. 编排逻辑与业务逻辑容易耦合

例如：

- Router 自己维护状态；
- Tool 自己输出事件；
- Agent 自己处理异常；
- FastAPI 接口负责拼装上下文；
- Memory 模块直接参与业务判断。

Harness 应把这些横切能力统一接管。

### 3. `[[ORCH]]` 事件还缺少统一 Schema

当前事件主要用于展示。

后续还需要同时服务于：

- 前端执行过程展示；
- 日志分析；
- Trace；
- 自动评估；
- Bad Case（失败案例）生成；
- 性能统计；
- 故障重放。

### 4. 缺少统一预算

不同 Agent 应当拥有不同预算，例如：

```text
知识解释：
max_steps = 3

代码审查：
max_steps = 10
max_tool_calls = 5

复杂数据分析：
max_steps = 20
max_duration = 10 分钟
```

### 5. 缺少结构化 RunResult（运行结果）

不应只返回字符串，而应返回：

```python
@dataclass
class RunResult:
    run_id: str
    status: str
    final_output: str

    artifacts: list
    citations: list
    tool_calls: list
    usage: Usage
    errors: list
```

---

# 七、LocalAgent 推荐的 Harness 分层

建议新增独立目录：

```text
localagent/
├── harness/
│   ├── agent_spec.py
│   ├── run_context.py
│   ├── run_state.py
│   ├── run_result.py
│   ├── runner.py
│   ├── agent_loop.py
│   ├── budgets.py
│   ├── lifecycle.py
│   ├── event_bus.py
│   ├── context_manager.py
│   ├── tool_registry.py
│   ├── policy_engine.py
│   └── exceptions.py
│
├── agents/
│   ├── core_router.py
│   ├── code_expert.py
│   ├── data_analyst.py
│   └── knowledge_expert.py
│
├── tools/
├── memory/
├── rag/
├── models/
└── api/
```

依赖关系应当是：

```text
FastAPI / PyQt6
        ↓
Harness Runner
        ↓
Agent Loop
   ┌────┼──────────┐
 Agent  Tools  Context Manager
   │      │          │
 Model  Sandbox   Memory / RAG
```

关键原则：

> FastAPI 只是入口，Agent 只是角色，Tool 只是能力；真正控制一次任务生命周期的必须是 Harness Runner。

---

# 八、第一轮重构不要直接重写整个 LocalAgent

推荐采用渐进式重构。

## 第一步：只统一运行模型

先增加：

```text
AgentSpec
RunContext
RunState
RunResult
RunBudget
```

暂时不修改现有 Agent 的核心逻辑。

## 第二步：增加 HarnessRunner

先让它包裹现有编排入口：

```python
result = await harness_runner.run(
    entry_agent="core_router",
    user_input=user_input,
    thread_id=thread_id,
)
```

内部仍可调用旧 Router。

## 第三步：统一事件

把现有 `[[ORCH]]` 事件转换为结构化事件，同时保留旧格式供 PyQt6 使用。

## 第四步：迁移一条最简单链路

优先迁移：

```text
普通知识解释
→ Router
→ Model
→ Final Answer
```

不要先迁移复杂 RAG 或 Excel Agent。

## 第五步：再接入工具和子 Agent

等基础 Run 模型稳定后，再迁移：

```text
代码审查
文本总结
RAG 问答
Excel 分析
多 Agent 协作
```

---

# 九、本阶段的验收目标

完成 Agent Harness 学习和改造后，LocalAgent 至少应做到：

1. 每个用户任务都有唯一 `run_id`。
2. 每个 Run 都有明确状态。
3. 每次模型调用和工具调用都有 `step_id`。
4. 所有 Agent 通过统一的 `HarnessRunner` 执行。
5. 所有工具通过统一 `ToolRegistry` 调用。
6. 每次运行都有最大步骤、时间和调用预算。
7. 所有事件使用统一 Schema。
8. 最终结果使用 `RunResult` 返回。
9. FastAPI 不再直接承担编排职责。
10. 自动评估平台可以直接消费 Run 和 Trace 数据。

---

# 十、本模块核心问题

## 1. Agent Harness 解决什么问题？

它解决的是 Agent 公共运行能力分散的问题，把模型调用、工具执行、状态管理、上下文构建、子 Agent 调度、安全策略、事件记录和结果返回组织成统一运行框架。

---

## 2. Agent Harness 与 Agentic Design Patterns 有什么区别？

设计模式描述 Agent 的行为组织方式；Harness 提供执行这些模式所需的统一工程环境。

例如 Planning 是一种模式，而：

- 计划保存在哪里；
- 计划步骤怎样执行；
- 每一步怎样记录；
- 中断后怎样继续；
- 超过最大步骤怎样终止；

这些属于 Harness 或 Runtime。

---

## 3. Agent Harness 与 Runtime 有什么区别？

Harness 更偏向 Agent 级别的装配和控制，Runtime 更偏向底层可靠执行。

```text
Harness：
Agent、工具、Prompt、上下文、循环、策略

Runtime：
持久化、恢复、队列、Worker、并发、调度
```

---

## 4. Agent Loop 为什么不能完全交给大模型？

因为模型无法可靠保证：

- 一定会终止；
- 不会重复调用；
- 不会超出预算；
- 不会调用危险工具；
- 不会生成非法参数；
- 不会忽略系统约束。

因此模型负责产生候选动作，Harness 负责校验、执行和限制动作。

---

## 5. RunContext 与 RunState 有什么区别？

```text
RunContext：本次运行依赖什么
RunState：本次运行进行到哪里
```

模型客户端、工具注册表、Memory Store 属于 Context；消息、计划、步骤、错误和工具结果属于 State。

---

## 6. 为什么 Harness 必须支持结构化事件？

因为同一份运行事件要同时支撑：

- 前端展示；
- 调试；
- 日志；
- Trace；
- 监控；
- 评估；
- 故障分析；
- Bad Case 回归。

只输出自然语言日志，无法稳定支撑这些系统。

---

# 十一、面试表达

## 30 秒版本

> 我把 Agent Harness 理解为智能体的统一运行框架。设计模式解决 Agent 如何规划、路由和调用工具，而 Harness 负责把模型、Agent、工具、上下文、状态、生命周期、安全策略和可观测性装配在一起。它的核心通常包括 AgentSpec、RunContext、RunState、Agent Loop、Tool Registry、预算控制、事件系统和结构化运行结果。

## 结合 LocalAgent 的项目版本

> 我的 LocalAgent 已经实现了 Router、多 Agent、RAG、SQLite 记忆、工具调用和 `[[ORCH]]` 事件，但早期这些能力分布在 FastAPI 接口、Agent 和工具模块中。后续我准备抽象独立的 Agent Harness 层，由 HarnessRunner 统一创建 Run，维护 RunContext 和 RunState，通过 ToolRegistry 调度工具，并使用结构化事件记录模型调用、工具调用、Handoff 和异常。这样可以进一步接入自动评估、链路追踪、预算控制以及后续的持久化恢复能力。

## 大厂面试加分表达

> 我不会让大模型直接控制完整执行流程。模型只负责产生下一步候选动作，Harness 负责 Schema 校验、权限检查、预算检查、工具执行和状态转移。这样可以把概率性的模型决策限制在确定性的工程边界内。

这句话可以作为 Agent 系统设计中的核心原则：

> **LLM proposes, Harness disposes。**

即：

> **大模型提出动作，运行框架决定是否以及怎样执行。**

---

# 十二、Agent Harness 学习拆分

接下来这一阶段建议拆成六个模块：

```text
Harness 1：概念、边界与整体架构
Harness 2：AgentSpec、RunContext、RunState、RunResult
Harness 3：Agent Loop、Tool Dispatch 与终止控制
Harness 4：Context Manager、Workspace 与 Artifact
Harness 5：Lifecycle Hooks、Event Bus 与 Policy Engine
Harness 6：可运行 Mini Harness Demo 与 LocalAgent 重构方案
```

当前已经完成 **Harness 1：概念、边界与整体架构**。

下一模块将重点实现四个最基础的数据模型：

```text
AgentSpec
RunContext
RunState
RunResult
```

并明确哪些状态应该持久化、哪些对象不能持久化，以及这些设计在 FastAPI 并发请求中的生命周期。