当前模型：GPT-5.6 Sol。

# LocalAgent Stage 2 学习总结

Stage 2 的核心不是“把 Agent 功能做多”，而是把原本可以运行但职责混杂的 Agent 调用链，重构成一套**有明确 Owner、有状态机、有失败语义、有资源生命周期、可审计、可测试的 Agent Runtime（智能体运行时）**。

后续 Stage 2.5 又补上了 Stage 2 初期遗漏的真实 Multi-Agent（多智能体）编排，因此整个 Stage 2 最终形成的是：

```text
Agent Harness / Runtime
+
真实 Multi-Agent Orchestration
+
Fault / Recovery / Observability / Lifecycle
+
Code-level Release Gate
```

Stage 2 原始 Runtime RC1 最终达到 `1089 passed + 42 subtests`，随后 Stage 2.5 多 Agent 收口后最终达到 `1412 passed + 42 subtests`，54/54 个必选 RC 场景通过。Stage 2 的最终结论仍然是 **code-level RC PASS**，不是生产环境容量或容灾认证。

------

# 一、Stage 2 最终学到了什么

最重要的一句话：

> **Agent Runtime 的核心不是调用 LLM，而是管理一次 Agent 执行从开始到结束的状态、资源、副作用、失败和事实边界。**

整个阶段实际上围绕五个问题展开：

```text
谁拥有这个状态？
谁允许它执行？
发生失败以后什么事实还能相信？
哪些操作可以重试？
Run 结束以后资源到底有没有真正释放？
```

这五个问题贯穿了 RunContext、AgentState、Scheduler、Tool、Journal、Recovery、Trace、Shutdown 和 Multi-Agent。

------

# 二、整个 Stage 2 的能力演进

## 第一部分：Runtime Foundation

首先建立最基本的运行时边界：

```text
RunContext
AgentState
AgentStateMachine
Plan / PlanStep
Scheduler
RunCoordinator
Cancellation
Deadline
Budget
```

关键学习点是：

### RunContext

描述“这一次运行是谁”。

包括：

- run identity；
- session / trace identity；
- deadline；
- cancellation token；
  -创建时间等。

它不是业务状态 Owner。

### AgentState

描述：

> “这次运行目前执行到哪里了？”

它成为 Runtime 动态状态的 **Single Source of Truth（单一事实来源）**。

因此：

```text
Plan = 做什么
AgentState = 做到哪里
```

PlanStep 不能再保存 Runtime Status，否则会形成双写。

这是 Stage 2 最重要的设计思想之一。

------

# 三、Owner 思维

Stage 2 最核心的工程方法可以概括成：

> **一个事实只能有一个 Owner。**

例如：

| 事实                      | Owner                          |
| ------------------------- | ------------------------------ |
| Runtime 状态              | AgentState / AgentStateMachine |
| Model Retry               | RetryExecutor                  |
| Model Candidate Fallback  | ModelInvocationRouter          |
| Event sequence            | RuntimeEventChannel            |
| Run terminal              | RunCoordinator                 |
| Tool Side-effect Evidence | AttemptSideEffectTracker       |
| Recovery 判断             | RecoveryValidator              |
| Shutdown 编排             | GracefulShutdownCoordinator    |

为什么这么设计？

因为如果多个模块都能够更新同一个事实，就容易产生：

```text
状态双写
重复执行
Retry 冲突
Terminal 重复
资源重复关闭
Recovery 得到不同答案
```

面试里可以总结成：

> 我设计 Runtime 时首先解决的不是模块划分，而是 Authority 和 Owner。只有把一个事实的唯一写入方确定下来，状态机、恢复、并发和故障处理才有可靠基础。

------

# 四、Model Runtime

Model 层最终明确分开了：

```text
Routing
Retry
Fallback
Timeout
Cancellation
Budget
Circuit Breaker
```

最重要的是区分：

## Retry

同一个 Candidate：

```text
DeepSeek
Attempt 1
→ fail
Attempt 2
```

Owner：

```text
RetryExecutor
```

## Fallback

不同 Candidate：

```text
Model A
→ fail
→ Model B
```

Owner：

```text
ModelInvocationRouter
```

## Runtime Fallback

这是另一回事：

```text
Coordinated
→ fail
→ Legacy
```

最终明确禁止这种自动行为。

原因是 Agent Runtime 可能已经：

-调用 Tool；
-写 Memory；
-产生外部 Side Effect；
-提交 Journal。

如果整个请求切换 Runtime 再执行一次，就可能造成重复副作用。

------

# 五、Timeout 与 Cancellation

这里学到的一个重要区别：

```text
Timeout
≠
Cancellation
```

Timeout 是时间条件。

Cancellation 是：

> Runtime 收到“应该停止”的控制信号。

Cancellation 采用：

```text
CancellationSource
→ CancellationToken
```

Source 只有生命周期 Owner 可以持有。

其他组件只看到 Token。

并采用：

```text
first-wins
```

第一个取消原因成为最终原因。

例如：

```text
CLIENT_DISCONNECTED
```

已经发生以后，后来的：

```text
TIMEOUT
```

不能覆盖它。

------

# 六、并发与 Worker

Stage 2 没有把 Parallelism（并行）理解成简单：

```python
asyncio.gather(...)
```

而是增加了：

```text
Scheduler
StepClaim
ParallelPolicy
Budget
Permit
Worker tracking
```

真正关键的问题变成：

> 谁允许一个 Step 开始执行？

答案：

```text
StepClaim
```

它是唯一执行授权。

这样可以避免 Driver、Agent、Scheduler 各自偷偷启动任务。

同时解决了同步 Worker 无法安全强杀的问题。

因此形成：

```text
active worker
detached worker
unknown worker
```

其中最重要的是：

> **不能因为 Timeout 发生，就假装同步线程已经停止。**

Detached Worker 必须继续可见。

------

# 七、Tool Runtime

Tool 是 Stage 2 中最接近真实生产系统的部分之一。

核心不是“调用函数”，而是：

```text
Invocation
Attempt
Idempotency
Lease
Permit
Side-effect Evidence
Retry
```

最重要的 Side Effect（副作用）状态：

```text
NOT_STARTED
STARTED
COMMITTED
UNKNOWN
COMPENSATED
```

核心原则：

```text
UNKNOWN ≠ NOT_STARTED
```

例如支付、写文件、发送请求：

```text
请求发送
→ 网络断开
→ 没收到结果
```

系统不能因为“没有收到成功响应”就认为：

```text
没有执行
```

因此对于非幂等 Tool：

```text
COMMITTED
UNKNOWN
```

都不能随意自动 Retry。

这对应一个非常经典的分布式系统思想：

> absence of evidence 不等于 evidence of absence。

Stage 2 也明确没有宣称系统级 Exactly-once（恰好一次）。

------

# 八、Retrieval Runtime

RAG 在 Runtime 中也被拆成阶段：

```text
Query Rewrite
→ Embedding
→ Vector Search
→ Rerank
→ Context Build
```

重要设计是失败不能统一处理。

### 可以降级

```text
Query Rewrite
Rerank
```

例如：

```text
Rerank 挂了
→ 可以继续使用原始召回顺序
```

### 必须 fail closed

```text
Embedding
Vector Search
```

因为：

```text
Vector DB 连接失败
```

不能被系统解释成：

```text
没有检索到资料
```

否则基础设施错误会被伪装成业务结果。

------

# 九、Journal-first

这是 Stage 2 最值得面试深入讲的设计之一。

最终事件链：

```text
RuntimeEvent
→ Journal append
→ Observability
→ Channel
→ Client
```

而不是：

```text
先发给客户端
→ 再考虑持久化
```

核心思想：

> **业务已经发生的事实和用户是否成功看见这个事实必须分开。**

例如：

```text
Tool 已执行
Journal 已提交
Channel 发送失败
```

系统不能：

```text
因为用户没收到
→ 重跑 Tool
```

这种情况叫：

```text
Partial Publication
```

因此：

```text
Journal
```

比客户端 Stream 更接近 Runtime Authority。

------

# 十、Event Contract

Event 体系解决三个核心问题：

### Identity

这个 Event 属于哪个 Run？

### Sequence

在 Run 中是第几个 Event？

### Terminal

Run 是否已经结束？

最终形成：

```text
RuntimeEventChannel
= sequence owner

RunCoordinator
= terminal owner
```

所以不能出现：

```text
Scheduler 发一个 RUN_COMPLETED
Driver 再发一个 RUN_COMPLETED
```

------

# 十一、Observability 与 Trace

Stage 2 还明确区分：

```text
Journal
Structured Log
Metrics
Trace
```

它们不是一回事。

### Journal

```text
运行事实
```

### Log

```text
排障
```

### Metrics

```text
聚合趋势
```

### Trace

```text
调用关系 + 延迟
```

最重要的设计原则：

> Observability 是 Derived Diagnostic（派生诊断），不是业务 Authority。

因此：

```text
Trace 写失败
Metrics 写失败
Logger 写失败
```

都不能：

```text
修改 AgentState
重跑 Tool
重跑 Model
改变 Run Terminal
```

当前 Structured Logger 已经是 RuntimeEvent 的安全 JSON 投影，而不是业务代码直接 `print()`；Stage 3 才会进一步生产化 Log Sink、轮转和外部 Collector。

------

# 十二、Trace 生命周期

Trace 中比较重要的是 ContextVar。

正常：

```text
parent span
  ↓
child span
  ↓
end
  ↓
恢复 parent context
```

曾经构造/发现过的重要问题：

```text
child span start 失败
→ 错误覆盖父 ContextVar
```

正确做法：

> start 失败也不能破坏已有调用上下文。

因此 Span 创建和 ContextVar restore 必须严格栈式对称。

------

# 十三、Snapshot 与 Recovery

这里最大的学习不是“如何恢复”，而是：

> **什么时候不能假装自己可以恢复。**

Snapshot 当前是：

```text
opt-in
```

保存的是安全状态摘要。

Recovery 当前只有：

```text
Recovery Validation
```

权威来源：

```text
Snapshot
+
Journal
```

RecoveryValidator 只能回答类似：

```text
这份 Snapshot 是否有效？
Journal tail 是否一致？
是否存在 Tool Side-effect Gap？
是否存在 Corruption？
```

它不能：

```text
调用 Model
调用 Tool
Replay
Resume
Compensation
```

所以当前明确：

```text
Recovery Validation
≠
Recovery Execution
```

这是很重要的 Production Awareness（生产意识）。

------

# 十四、Graceful Shutdown

Shutdown 最重要的学习点：

```text
流程执行结束
≠
资源真的全部关闭
```

因此：

```text
orchestration_completed
≠
fully_closed
```

典型 Shutdown：

```text
停止接收新 Run
→ Cancel active runs
→ Drain runs
→ Stop worker admission
→ Drain workers
→ Flush
→ Close resources
```

如果 Worker 仍然：

```text
detached
unknown
```

那么共享 Model Client 不能直接关闭。

因此：

```text
Model Close
```

必须经过 Worker Safety Gate。

------

# 十五、Fault Injection

Stage 2 建立的不是随机 Chaos Monkey，而是：

```text
Deterministic Fault Injection
```

即人为精确控制：

```text
在 Model before invoke 失败
在 Journal append 后失败
在 Snapshot save 后取消
在 Trace start 时失败
在 Shutdown worker drain 前失败
```

作用不是模拟“随机世界”，而是系统性验证不可逆边界。

Stage 2 原始最终统计：

```text
42 Fault Points
32 Supported
10 Contract-only
```

后来 Stage 2.5 随多 Agent 扩展到更多 Fault Point。

生产 Fault Injection 仍然未实现。

------

# 十六、Stage 2.5：Multi-Agent 补全

Stage 2 前半段最大的架构缺口是：

> Runtime 工程能力迁到了 Coordinated，但 Legacy 的角色化 Multi-Agent 没有一起迁移。

Stage 2.5 最终补上了这个问题。

完整链：

```text
User Request
→ Planner
→ Plan
→ Scheduler
→ Specialist Agents
→ StepResultStore
→ Synthesis Agent
→ OutputGate
→ Final Output
```

Agent Registry 包含类似：

```text
core_router
knowledge_expert
code_expert
data_analyst
synthesis_agent
```

------

# 十七、Multi-Agent 最重要的设计：Aggregation

多 Agent 最大的问题不是调用多少 Agent，而是：

> **多个 Agent 的结果谁能看到，最终谁负责回答？**

最终不是：

```text
Agent A output
Agent B output
Agent C output
→ 字符串拼接
```

而是：

```text
Specialist
→ StepResult
→ StepResultStore
→ dependency-scoped view
→ Synthesis
```

Synthesis 只能读取它声明依赖的结果。

不能读取：

-全量 StepResultStore；
-全量 Memory；
-Journal；
-Trace；
-Planner Raw Output。

这是最小权限原则在 Agent Context 中的应用。

------

# 十八、Final Output

Stage 2.5 又进一步解决：

> 多个 Agent 到底谁有权向用户输出？

最终由：

```text
OutputGate
```

成为 final publication Owner。

Specialist：

```text
INTERNAL
```

不能直接输出给用户。

只有最终 Synthesis：

```text
FINAL
```

才能经过 OutputGate。

并且：

```text
Delivery
≠
Execution
```

Agent 执行成功，不代表用户一定收到。

只有：

```text
DELIVERED
```

的最终回答才能写入 Conversation Memory。

------

# 十九、Memory 写入

最终形成：

```text
Specialist result
→ 不写 conversation memory

Synthesis result
→ OutputGate

DELIVERED
→ atomic user/assistant exchange commit
```

因此避免：

```text
knowledge_expert 中间结果
code_expert 中间结果
data_analyst 中间结果
```

污染用户对话 Memory。

------

# 二十、Stage 2 高价值 Bad Cases

最值得面试准备的是这些：

### 1. Plan / AgentState 双写

根因：

```text
定义数据
+
运行数据
```

职责混乱。

知识点：

```text
Single Source of Truth
```

### 2. UNKNOWN Side Effect 被当作 NOT_STARTED

风险：

```text
重复执行外部副作用
```

知识点：

```text
Idempotency
irreversible boundary
```

### 3. RunScope 创建但没 execute 导致 Registry 泄漏

知识点：

```text
resource acquire
必须有
symmetric release
```

### 4. EventPublicationError 保存完整 RuntimeEvent

风险：

```text
敏感正文泄漏
对象生命周期延长
```

最终只保存安全 Evidence。

### 5. Trace Start 失败擦除父 Context

知识点：

```text
ContextVar lifecycle
```

### 6. Worker Drain 未执行却被认为 Idle

核心：

```text
没有看到 worker
≠
已经证明 worker 不存在
```

### 7. Model Alias 绕过 Close Gate

说明生命周期判断必须按：

```text
object identity
```

而不是资源名称。

### 8. Shutdown completed 被误解为 fully closed

知识点：

```text
流程事实
≠
资源事实
```

这些高价值案例均被专门整理，并严格区分真实开发发现与假设构造，没有包装成生产事故。

------

# 二十一、名词 / 概念速览

| 名词                | 一句话理解                                |
| ------------------- | ----------------------------------------- |
| Runtime             | 管理 Agent 一次完整执行生命周期的运行环境 |
| RunContext          | 一次 Run 的不可变上下文                   |
| AgentState          | Runtime 动态状态唯一事实源                |
| Plan                | 不可变执行定义                            |
| Scheduler           | 判断什么时候哪个 Step 可以执行            |
| StepClaim           | Scheduler 发出的唯一执行授权              |
| Retry               | 同一个候选执行多次                        |
| Fallback            | 在候选之间切换                            |
| Cancellation        | 主动终止正在进行的 Run                    |
| Deadline            | Run 最晚允许执行到什么时候                |
| Budget              | 对 Token、Tool、Retry 等资源进行约束      |
| Idempotency         | 重复执行是否产生相同外部效果              |
| Side Effect         | 系统外部不可轻易回滚的影响                |
| Journal             | Append-only 的运行事实记录                |
| Event               | Runtime 对外表达发生了什么                |
| Trace               | 表达调用链父子关系和耗时                  |
| Snapshot            | 某个时间点的安全状态投影                  |
| Recovery Validation | 判断是否可以恢复，而不是执行恢复          |
| Detached Worker     | Runtime 已停止等待，但底层线程仍运行      |
| Graceful Shutdown   | 有顺序地停止新请求、Drain 并关闭资源      |
| Fault Injection     | 人为在指定执行接缝注入故障                |
| Agent Registry      | Agent 身份和 Capability 的事实目录        |
| StepResultStore     | Multi-Agent 中间结果的受控存储            |
| Synthesis           | 聚合多个 Specialist 结果形成最终回答      |
| OutputGate          | Run 级最终答案发布 Owner                  |

------

# 二十二、工程方法类高频面试题

## 为什么 Plan 和 State 要分离？

因为 Plan 是静态执行定义，而 State 是动态运行事实。

如果两边都保存 Step Status，就会形成双写。

------

## 为什么不做 Runtime Fallback？

因为请求可能已经产生 Tool、Memory 或外部副作用。

整个 Runtime 重跑无法安全判断哪些动作已经发生。

------

## 为什么 Journal-first？

为了把：

```text
业务是否已经发生
```

与：

```text
客户端是否收到
```

分开。

------

## 为什么 Recovery 只做 Validation？

因为没有：

```text
Durable Executor
Result Rehydration
完整 Side-effect Recovery
```

就直接 Resume，会制造错误安全感。

------

## 为什么 Trace/Log failure 不能影响业务？

因为 Observability 本质是派生信息。

如果日志异常能导致业务失败甚至 Retry，就形成了错误的反向依赖。

------

## 为什么 UNKNOWN 不能重试？

因为 UNKNOWN 表示：

> 外部操作可能已经成功。

重试可能产生重复副作用。

------

## 为什么同步 Worker 不能 Timeout 后直接删除？

Python 不能安全强杀普通正在执行的线程。

删除记录只是在监控层“看不见”，不代表线程停止。

------

## 为什么 Multi-Agent 要做 Dependency Scoped Result？

为了避免：

```text
上下文污染
越权读取
无关结果进入 Prompt
Token 膨胀
```

同时让 Plan dependency 真正成为数据依赖关系。

------

# 二十三、30 秒面试总结

> Stage 2 我主要把 LocalAgent 原本职责混杂的 Agent 调用链改造成了一套显式 Runtime。核心是建立 RunContext、AgentState、Scheduler、Budget、Timeout、Cancellation 等统一执行合同，再对 Model、Tool、Retrieval 的重试和失败语义做分层治理。事件采用 Journal-first，Observability 和 Trace 只作为派生诊断，Snapshot 当前只支持只读 Recovery Validation。后续 Stage 2.5 又把 Legacy 的多 Agent 编排迁到了默认 Coordinated Runtime，通过 Agent Registry、StepResultStore、Synthesis 和 OutputGate 完成真实并行多 Agent 执行和唯一最终输出。

------

# 二十四、2 分钟面试总结

> Stage 2 的目标是把 LocalAgent 从“能够调用 Agent”提升成“能够可靠运行 Agent”。首先我建立 RunContext 和 AgentState，把 Runtime 动态状态统一交给 AgentStateMachine，Plan 只保留静态定义。Scheduler 使用 StepClaim 作为唯一执行授权，同时统一管理 Budget、Deadline、Cancellation 和 Parallel Execution。
>
> Model 层把 Retry 和 Candidate Fallback 分开；Tool 层引入 Invocation、Attempt、Idempotency 和单调 Side-effect Evidence，尤其 UNKNOWN 不允许降级成 NOT_STARTED，避免非幂等 Tool 被重复调用。Retrieval 也区分可以降级的 Rewrite/Rerank 和必须 fail closed 的 Embedding/Search。
>
> 事件系统采用 Journal-first，业务事实先持久化，再投影到 Streaming、Metrics 和 Trace，所以客户端发送失败不会导致已经提交的业务重做。Snapshot 当前只做安全状态投影，RecoveryValidator 只读取 Snapshot + Journal，不做 Replay 或 Resume。
>
> 生命周期方面还处理了 Client Disconnect、Detached Worker 和 Graceful Shutdown，明确 orchestration completed 不等于 fully closed。
>
> Stage 2.5 又补齐了真实 Multi-Agent：Planner 生成 Frozen Plan，Scheduler 并行调用多个 Specialist，把结果存入 StepResultStore，Synthesis 只能读取显式依赖结果，最后由 OutputGate 唯一发布 Final Answer，并且只有 DELIVERED 的最终回答才写入 Memory。

------

# 二十五、当前 Truth / Completion Boundary

### 已真实完成

- Coordinated Runtime；
- RunContext / AgentState；
  -Scheduler / Parallel；
  -Budget / Timeout / Cancellation；
  -Model Retry / Fallback / Circuit；
  -Tool Runtime；
  -Retrieval Runtime；
  -Journal-first Event；
  -Observability / Trace；
  -Snapshot；
  -Recovery Validation；
  -Worker Lifecycle；
  -Graceful Shutdown；
  -确定性 Fault Injection；
  -Multi-Agent Registry；
  -Specialist Parallel Execution；
  -StepResultStore；
  -Synthesis；
  -OutputGate；
  -DELIVERED-only Memory；
  -Contract / RC Gate。

### 明确没有完成

- Recovery Execution；
  -Replay / Resume；
  -Step Result Rehydration；
  -Cross-process Registry；
  -Distributed Exactly-once；
  -Automatic Compensation；
  -Production Fault Injection；
  -Random Chaos。

### 当前接受的主要 P2

Stage 2.5 最终仍接受：

```text
Planning 与 Specialist 共用 bounded executor
→ 可能存在 Planning starvation
```

当前已经保证 Deadline、Cancellation 和 Event Loop 不被错误阻塞，但容量风险仍保留。

------

# 二十六、你现在应该真正记住的 8 个关键词

如果 Stage 2 最后只保留八个面试关键词，我建议是：

```text
Owner
Single Source of Truth
State Machine
Journal-first
Idempotency
Cancellation
Recovery Validation
Graceful Shutdown
```

Multi-Agent 再补两个：

```text
Dependency-scoped Aggregation
OutputGate
```

它们基本可以串起整个 Stage 2 的架构故事。

------

## 推荐学习文档文件名

```text
docs/interview/stage2_runtime_multi_agent_learning_summary.md
```

Stage 2 最值得形成的个人认知不是“我实现了一堆 Runtime 类”，而是：

> **一个 Agent 系统真正走向工程化以后，核心问题会从 Prompt 和调用模型，转变为 Ownership、状态、不可逆副作用、并发、事实持久化、故障隔离和生命周期。**

这也是 Stage 2 对后续 Stage 3 生产化、AgentEvalOps、Tool/MCP、高级 RAG/Memory 最重要的基础。