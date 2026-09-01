# Stage5-Phase0-WP1 学习 / 面试总结

## 1. 一句话项目定义

这一 WP 解决的问题可以概括成：

> 我为 AgentEvalOps 增加了一个面向 LocalAgent 的 HTTP ExecutionTarget（HTTP 执行目标），让评估系统可以通过真实 HTTP 边界调用 LocalAgent 的 Coordinated Runtime（协调式运行时），并把运行终态可靠地映射为统一的 `ExecutionOutcome`，从而为后续 RAG Baseline（检索增强生成基线）、Candidate 对比和自动回归建立真实执行桥梁。

这里最重要的关键词不是“HTTP 调用”。

而是：

```text
Evaluation System
        ↓
ExecutionTarget
        ↓
Anti-Corruption Layer（防腐层）
        ↓
Agent Runtime
```

它本质上是在两个独立系统之间建立一个**受控协议边界**。

------

# 2. 为什么这个 WP 是 Stage 5 的第一个阻塞点

Stage 4 已经完成了：

```text
Dataset
EvaluationRun
ExecutionAttempt
ExecutionResult
Comparison
RegressionReport
ReleaseDecision
```

这些 Evaluation Core（评估核心）。

但当时唯一真正存在的 Concrete Target（具体执行目标）是：

```text
FixtureExecutionTarget
```

也就是测试 Fixture（测试夹具）。

因此：

```text
Evaluation Framework 已经存在
≠
已经能真实评估 LocalAgent
```

没有 WP1：

```text
固定 Dataset
     ↓
AgentEvalOps
     ↓
???
     ↓
LocalAgent
```

中间缺一座桥。

后面的：

- RAG Artifact；
- RAG Dataset；
- Recall@K；
- MRR；
- NDCG；
- Baseline / Candidate；
- Regression Gate；

都只能停留在框架层。

所以 WP1 是一个典型的：

> **Evaluation Infrastructure（评估基础设施）已经完成，但 System Under Test（被测系统）还没有真正接入。**

------

# 3. 最终架构

最终架构不是直接：

```text
AgentEvalOps
→ LocalAgent KnowledgeExpert
```

也不是：

```text
AgentEvalOps
→ LocalAgent RetrievalService
```

而是：

```text
EvaluationLoopService.execute_attempt
        ↓
ExecutionTargetResolver
        ↓
LocalAgentHttpExecutionTarget
        ↓
POST /api/runtime/execute
        ↓
ChatService.run_coordinated_agent
        ↓
CoordinatedRuntimeFactory
        ↓
CoordinatedRunScope
        ↓
RunCoordinator
        ↓
Planner / Scheduler / Agent
        ↓
Tool / Retrieval
        ↓
StepResultStore
        ↓
OutputGate
        ↓
RunCoordinatorResult
        ↓
Structured HTTP Response
        ↓
ExecutionOutcome
        ↓
EvaluationPersistenceService.record_outcome
```

Final Gate 已确认没有出现第二套 Runtime、第二套 terminal state 或 Evaluation Domain。

------

# 4. 最值得理解的设计：为什么不能直接复用 `/api/chat`

LocalAgent 已有：

```text
POST /api/chat
```

最直觉的做法当然是：

```text
AgentEvalOps
→ POST /api/chat
→ 收文本
→ 判断成功
```

但这实际上有严重问题。

`/api/chat` 是：

```text
text/plain StreamingResponse
```

它适合：

> 给用户持续显示生成文本。

却不适合：

> 给另一个后端系统提供精确的 execution terminal fact（执行终态事实）。

因为：

```text
stream EOF
```

不能准确区分：

```text
SUCCEEDED
FAILED
CANCELLED
CLIENT_DISCONNECTED
DELIVERY_FAILED
```

例如连接断了，你不能知道：

```text
模型没执行？
已经执行但响应丢了？
Run 已经成功？
Run 被取消？
```

所以：

> 面向用户的 Streaming API（流式接口）和面向机器评估系统的 Execution API（执行接口）可以共享同一个 Runtime，但不一定应该共享同一个 Wire Protocol（线协议）。

这是这个 WP 很值得面试讲的一点。

------

# 5. 为什么不使用 Trace 判断执行成功

Scout 阶段发现一个看起来很诱人的方案：

```text
HTTP 调 LocalAgent
    ↓
获取 run_id
    ↓
等待 Trace
    ↓
看 final_status
```

但最后明确拒绝。

因为 Trace Contract v1 的 delivery semantics（投递语义）是：

```text
BEST_EFFORT
+
AT_MOST_ONE_TRANSPORT_ATTEMPT_PER_ACCEPTED_ENVELOPE
```

这并不意味着：

```text
guaranteed exactly-once delivery
```

如果把 Trace 当同步执行结果：

```text
LocalAgent 实际执行成功
        ↓
Trace 网络发送失败
        ↓
AgentEvalOps 没看到 Trace
        ↓
误判执行失败
```

就变成了：

> **Observability（可观测性）决定 Execution Correctness（执行正确性）。**

这属于明显的职责倒置。

最终正确边界是：

```text
RunCoordinatorResult
= execution terminal truth
Trace
= evidence / observability / debugging
```

Trace 丢失：

```text
≠
执行失败
```

Final Gate 也重新确认 Adapter 完全不依赖 Trace polling、trace repository 或 `trace_id`。

------

# 6. 为什么新增 `/api/runtime/execute`

最终增加：

```text
POST /api/runtime/execute
```

它不是第二套 Runtime。

它只是：

```text
RunCoordinatorResult
→ HTTP JSON projection
```

Request：

```json
{
  "agent_id": "core_router",
  "query": "...",
  "run_id": "...",
  "timeout_seconds": 30.0
}
```

Response：

```json
{
  "run_id": "...",
  "status": "SUCCEEDED",
  "stop_reason": "COMPLETED",
  "error_code": null,
  "safe_message": null
}
```

非常关键的一点：

### HTTP 200 不等于 Runtime 成功

例如 LocalAgent 真正执行完成，但执行结果是：

```text
FAILED
```

HTTP 仍可以是：

```text
200
```

body：

```text
status = FAILED
```

为什么？

因为需要区分两个层次：

```text
HTTP / Protocol Success
```

和：

```text
Agent Runtime Success
```

也就是说：

> HTTP 200 表示“我成功完成了这次执行协议，并告诉你 Agent 的终态”，而不是“Agent 一定执行成功”。

这是标准的**协议状态与业务状态分离**。

------

# 7. 最核心的 Owner 设计

这个 WP 很适合用来回答：

> “复杂系统中怎么避免职责混乱？”

最终 Owner Matrix（所有权矩阵）非常清楚。

| Concern                     | Owner                                        |
| --------------------------- | -------------------------------------------- |
| EvaluationRun lifecycle     | `EvaluationPersistenceService`               |
| ExecutionAttempt lifecycle  | `EvaluationPersistenceService`               |
| Target resolution           | `ExecutionTargetResolver`                    |
| HTTP invocation             | `LocalAgentHttpExecutionTarget`              |
| Evaluation outer timeout    | `LocalAgentHttpExecutionTarget`              |
| HTTP transport timeout      | `LocalAgentHttpExecutionTarget`              |
| LocalAgent Runtime deadline | `RunContext / RunCoordinator`                |
| LocalAgent terminal state   | `RunCoordinator`                             |
| timeout 后 remote cleanup   | `LocalAgentHttpExecutionTarget`              |
| Remote cancellation         | `RunRegistry`                                |
| Evaluation retry            | `EvaluationPersistenceService.retry_attempt` |
| Trace correlation           | AgentEvalOps Trace integration               |
| Tool execution              | `ToolExecutionService`                       |
| Retrieval execution         | `RetrievalExecutionService`                  |

最重要的是：

```text
Target 可以调用 Owner
≠
Target 自己成为 Owner
```

例如：

```text
LocalAgentHttpExecutionTarget
→ 调 /cancel
```

不代表：

```text
LocalAgentHttpExecutionTarget
= Cancellation Owner
```

真正修改 LocalAgent cancellation state 的仍然是：

```text
RunRegistry / CancellationSource
```

------

# 8. Timeout 为什么不能只写一个 `httpx.Timeout(30)`

这是 WP1 最重要的后端设计题之一。

这里存在三种不同 timeout：

```text
Evaluation Attempt timeout
HTTP Transport timeout
LocalAgent Runtime deadline
```

如果设计不好，很容易：

```text
Evaluation timeout = 60s
HTTP timeout = 120s
Runtime timeout = 300s
```

然后谁先终止、谁取消谁，完全混乱。

最终设计：

```text
Evaluation outer deadline
        ↓
        ├── HTTP transport timeout
        │       <= remaining outer deadline
        │
        └── LocalAgent runtime timeout_seconds
                <= remaining outer deadline
```

即：

```text
provider_timeout =
min(remaining_evaluation_timeout, 3600.0)
```

本质是：

> **所有下层 timeout 都必须服从一个上层 Deadline（截止时间）。**

而不是三个独立 Stopwatch（计时器）。

这是 Deadline Propagation（截止时间传播）的核心思想。

------

# 9. TIMEOUT 和 CANCELLED 为什么必须区分

假设：

```text
Evaluation timeout = 30 秒
```

30 秒到了。

AgentEvalOps：

```text
停止等待
```

然后为了避免 LocalAgent 继续浪费资源：

```text
POST /api/runtime/runs/{run_id}/cancel
```

这时真正的根因仍然是：

```text
EVALUATION_TIMEOUT
```

不能因为 cleanup 调用了 cancel 就改成：

```text
CANCELLED
```

正确语义：

```text
Evaluation Deadline Reached
        ↓
ExecutionOutcome.TIMEOUT
        ↓
best-effort remote cancel
        ↓
cleanup status 只记录 metadata
```

即使：

```text
cancelled
already_cancelled
inactive
cancel failed
cancel timeout
```

原始 outcome 仍然：

```text
TIMEOUT / EVALUATION_TIMEOUT
```

这体现一个很重要的工程原则：

> **Cleanup（清理动作）不能覆盖 Root Cause（根因）。**

------

# 10. `asyncio.CancelledError` 又为什么不同

还有另一种情况：

```python
task.cancel()
```

这不是：

```text
Evaluation deadline exceeded
```

而是调用方直接取消当前 Coroutine（协程）。

因此 Adapter 的行为是：

```text
收到 CancelledError
        ↓
如果远端可能已经执行
    best-effort /cancel
        ↓
重新 raise 原始 CancelledError
```

不能：

```text
return ExecutionOutcome.CANCELLED
```

因为：

> 调用当前 coroutine 被取消，不代表已经观察到了远端 LocalAgent 的 `RunStatus.CANCELLED`。

这是**本地控制流事实**和**远程业务事实**的区别。

------

# 11. 本 WP 最有价值的 Bad Case：Ambiguous Transport

这个案例强烈建议作为面试主案例。

## 场景

AgentEvalOps：

```text
POST /api/runtime/execute
```

LocalAgent：

```text
已经收到请求
已经开始执行
```

然后：

```text
TCP connection reset
```

AgentEvalOps 没收到响应。

现在你知道什么？

只知道：

```text
响应没回来
```

但不知道：

```text
远端到底有没有执行
```

如果直接：

```text
FAILURE
→ retry
```

可能变成：

```text
第一次请求其实已经执行 Tool
        ↓
网络断了
        ↓
自动 retry
        ↓
Tool 第二次执行
```

如果 Tool 是：

```text
发送邮件
删除数据
创建工单
支付
写文件
```

就会产生 Duplicate Side Effect（重复副作用）。

所以最终：

```text
OutcomeKind.OUTCOME_UNKNOWN
error_category = HTTP_AMBIGUOUS_TRANSPORT
```

并且：

```text
NO AUTOMATIC RETRY
```

Final Gate 也专门重新确认这一行为没有漂移。

------

# 12. 为什么不是 FAILURE

这是面试官很可能追问的。

### Connection refused

如果连接压根没建立：

```text
可以基本确定远端没执行
```

所以：

```text
FAILURE
HTTP_CONNECTION_FAILURE
```

### Read reset

如果：

```text
request 已经 write 出去
```

然后读 response 时 reset：

```text
不能知道远端有没有执行
```

所以：

```text
OUTCOME_UNKNOWN
```

核心区别不是：

```text
网络错误类型
```

而是：

> **我们是否能够确定远端执行事实。**

这也是 Distributed Systems（分布式系统）里非常典型的 Unknown Outcome（未知结果）问题。

------

# 13. 为什么禁止 HTTP 自动 Retry

因为 LocalAgent 当前没有 Remote Idempotency（远端幂等）保证。

没有：

```text
idempotency key
dedup store
exactly-once execution
```

所以：

```text
ambiguous request
→ retry
```

是不安全的。

这里保留：

```text
EvaluationPersistenceService.retry_attempt
```

作为 Evaluation-level Retry（评估级重试）。

它会：

```text
创建新的 Attempt
产生新的 Attempt ID
保留 retry provenance
```

从而明确知道：

```text
这是一次新的评估尝试
```

而不是 HTTP Client 偷偷把同一 Attempt 执行两遍。

------

# 14. 为什么 run_id 使用 Attempt ID

AgentEvalOps：

```text
EvaluationRun
```

可以包含很多：

```text
ExecutionAttempt
```

如果：

```text
LocalAgent run_id = EvaluationRun.run_id
```

多个 case / retry 会共享 LocalAgent Run ID。

这是错误的。

最终：

```text
LocalAgent run_id
=
ExecutionAttempt.attempt_id
```

因此形成：

```text
EvaluationRun
    ↓
ExecutionAttempt
    ↓
LocalAgent run
    ↓
Artifact
    ↓
Evidence
```

同一条 identity chain。

Retry 时：

```text
Attempt #1 → LocalAgent Run A
Attempt #2 → LocalAgent Run B
```

天然隔离。

------

# 15. ArtifactRef 为什么只保存 Run Identity

`ExecutionOutcome.SUCCESS` 当前 Contract 强制要求：

```text
output_artifact_ref != None
```

但 WP1 又没有做：

```text
RAG Artifact
Final Answer Artifact
Artifact Store
```

所以最终使用：

```text
ArtifactRef(
    artifact_id="localagent-run://<attempt_id>",
    media_type="application/vnd.localagent.execution-ref+json"
)
```

这里一定要注意表达：

> 它不是“答案文件”。

它表示：

> **一个成功执行产生的 LocalAgent execution identity artifact。**

这是一个最小桥接。

完整：

```text
retrieved_items
citations
rewritten_query
latency
```

属于 WP2。

------

# 16. `Execution SUCCESS != Evaluation PASS`

这是 Stage 5 后面必须牢牢记住的一条。

```text
ExecutionOutcome.SUCCESS
```

只表示：

> LocalAgent Runtime 成功执行完成。

不代表：

> 回答质量好。

例如：

```text
用户问：CDT 字段映射是什么？
```

LocalAgent 正常跑完，但回答完全错误：

```text
Execution = SUCCESS
Evaluation = FAIL
```

所以：

```text
Execution
        ↓
如果 SUCCESS
        ↓
Evaluator
        ↓
EvaluationResult
```

而：

```text
Runtime execution success
```

绝不能直接生成：

```text
Evaluator PASS
```

Final Gate 也验证了 structured failure 不生成正常 EvaluationResult。

------

# 17. Production Runtime Path 的真实性边界

这是本次 Final Gate 特意修正的一个表达。

Live E2E 实际证明：

```text
真实 AgentEvalOps EvaluationLoop
→ 真实 LocalAgentHttpExecutionTarget
→ 真实 HTTP
→ 真实 LocalAgent /api/runtime/execute
→ 真实 structured protocol
→ 真实 PostgreSQL persistence
```

但 provider Runtime 使用：

```text
FakeRouter
scripted _StubScope
```

所以不能说：

> “我跑通了真实模型完整生产 E2E。”

正确表达：

> 我跑通了真实跨仓 HTTP 和 Evaluation persistence E2E；Provider 内模型执行使用 deterministic test runtime fixture。真实 production Runtime path 则通过 endpoint wiring、真实 `CoordinatedRuntimeFactory` 测试和 `RunCoordinator` 回归测试形成组合证据。

Final Gate 将 AC1/AC3 明确标为：

```text
PASS — COMBINED_EVIDENCE
```

而不是把 stub E2E 冒充 full production Runtime E2E。

这个真实性边界非常适合面试。

------

# 18. 测试体系是怎么分层的

这次验证不是简单一句：

```text
pytest passed
```

而是三层。

## Unit Test（单元测试）

证明：

```text
协议映射
异常分类
timeout
cleanup
no retry
Resolver
Settings
```

Final Gate 重跑：

```text
118 passed
```

------

## Integration Test（集成测试）

证明：

```text
真实 PostgreSQL
真实 EvaluationRun
真实 ExecutionAttempt
真实 EvaluationPersistenceService
真实 HTTP transport
```

重点确认：

```text
record_outcome
ArtifactRef
EvidenceRef
Run terminal
```

真实持久化。

------

## Cross-Repository HTTP E2E（跨仓 HTTP 端到端）

证明：

```text
AgentEvalOps
→ real HTTP
→ LocalAgent endpoint
→ structured terminal protocol
→ PostgreSQL
```

但明确保留 test runtime fixture 边界。

这种测试分层比“跑一个超级大的 E2E”更容易定位问题。

------

# 19. Settings / Resolver 为什么值得单独设计

最终：

```text
target_version_ref
```

表示：

```text
LocalAgent HTTP execution protocol/profile version
```

例如：

```text
v1
```

而：

```text
config_ref
```

表示：

```text
localagent-coordinated-v1
```

只是 Configuration Identity（配置身份）。

真正：

```text
LOCALAGENT_HTTP_BASE_URL
```

在 Settings。

这意味着：

```text
Identity
```

和：

```text
Runtime Location
```

分离。

所以不能：

```text
config_ref = "http://10.x.x.x:8000"
```

否则：

- 泄露内部地址；
- 环境不可迁移；
- Baseline / Candidate attribution 混乱。

------

# 20. 这一 WP 没有做什么

面试时这部分也非常重要。

没有做：

```text
Production Evaluation API
Celery evaluation worker
Remote idempotency
Exactly-once execution
Evaluation cancel API
Artifact Store
RAG Artifact
RAG Dataset
RAG Evaluator
Trace durable outbox
Target Registry
Service Discovery
```

不是遗漏，而是明确的：

```text
Scope Boundary
```

最终 Final Gate 仍保留这些 Known Limitations。

------

# 21. 面试最值得讲的 5 个设计决策

建议优先掌握下面五个。

### ① 为什么新增 `/api/runtime/execute`，不直接复用 `/api/chat`？

因为 Streaming UI protocol 无法可靠表达机器需要的结构化 terminal state；新 endpoint 复用同一 Runtime，只新增 wire projection。

### ② 为什么不用 Trace 判断执行状态？

Trace 是 BEST_EFFORT Observability，不应该成为同步 execution correctness 的依赖。

### ③ 为什么网络断开有时是 FAILURE，有时是 OUTCOME_UNKNOWN？

关键不是网络错误名称，而是能不能证明远端没有执行。

### ④ 为什么 timeout 后 cancel，但 outcome 还是 TIMEOUT？

cancel 是 cleanup，timeout 才是 root cause；cleanup 不应覆盖根因。

### ⑤ 为什么禁止 HTTP 自动 retry？

因为没有 remote idempotency；ambiguous transport 自动 retry 可能造成重复 Tool 副作用。

这五个问题基本覆盖了该 WP 80% 的面试价值。

------

# 22. 可直接用于面试的完整回答

如果面试官问：

> “你们的评估系统是怎么调用真实 Agent 的？”

你可以回答：

> 我们 Evaluation Core 本身通过 `ExecutionTarget` 抽象隔离被测系统。最开始只有 Fixture Target，所以 Stage 5 第一件事就是实现 LocalAgent HTTP ExecutionTarget。
>
> 这里我没有直接复用聊天用的 `/api/chat`，因为它是 text streaming protocol，流结束没法可靠区分 Runtime 成功、失败、取消和连接异常。所以我在 LocalAgent 增加了一个非 breaking 的 `/api/runtime/execute`，它不创建第二套 Runtime，只把既有 `RunCoordinatorResult` 投影成结构化 JSON。`RunCoordinator` 仍然是 terminal state 的唯一 Owner。
>
> AgentEvalOps 侧的 HTTP Target 负责协议转换和 failure normalization，比如 HTTP 4xx/5xx、timeout 和 malformed response。一个比较关键的设计是，我们把“请求可能已经到远端，但响应丢失”的场景定义成 `OUTCOME_UNKNOWN`，而不是 FAILURE，也禁止自动 retry。因为 LocalAgent 没有 remote idempotency，如果第一次其实已经执行了 Tool，再自动重发可能导致重复副作用。
>
> timeout 方面我们用了 deadline propagation。`ExecutionRequest.timeout` 是 Evaluation outer deadline，HTTP transport 和 LocalAgent runtime deadline 都从它的 remaining budget 推导。Evaluation timeout 后可以 best-effort 调 LocalAgent cancel 做资源清理，但最终 outcome 仍然是 TIMEOUT，因为 cancellation 只是 cleanup，不能覆盖原始 root cause。
>
> 另外 Trace 没有参与同步结果判断。我们的 Trace 是 BEST_EFFORT observability，所以如果让 Trace 决定 execution success，Trace 丢失反而会被误判成 Agent 执行失败。最终 Trace 只作为异步 Evidence。
>
> 验证上我们分了 unit、PostgreSQL integration 和 cross-repository HTTP E2E。Final Gate 是 P0=0、P1=0。跨仓 E2E 使用 deterministic runtime fixture，所以我不会把它描述成真实模型生产 E2E；完整 Runtime path 是结合真实 HTTP E2E、Factory/RunCoordinator 测试和源码 wiring 做组合验证的。

这段是目前最推荐你掌握的版本。

------

# 23. 高频追问题

### Q1：为什么 `OUTCOME_UNKNOWN` 不直接记 FAILURE？

因为 FAILURE 意味着我们已经有证据确认执行失败；网络响应丢失时可能远端已经执行成功，所以只能保留未知事实。

### Q2：那 UNKNOWN 怎么处理？

当前不自动重试。后续由 Evaluation 层显式决定是否创建新的 retry Attempt，并保留新的 Attempt identity 和 provenance。

### Q3：为什么不做 idempotency？

不是 WP1 blocker，而且通用幂等需要远端持久化、dedup 生命周期和副作用语义，Scope 很容易膨胀。当前用 `OUTCOME_UNKNOWN + no retry` 保证真实性。

### Q4：HTTP Target 为什么不是 Runtime Owner？

它只负责 Protocol Mapping（协议映射）。真实 LocalAgent terminal state 仍由 `RunCoordinator` 产生。

### Q5：你们怎么保证 Baseline/Candidate 公平？

ExecutionTarget 的：

```text
target_id
target_kind
target_version_ref
config_ref
payload schema
timeout semantics
retry semantics
```

保持固定，避免 Adapter 本身成为隐藏实验变量。

------

# 24. Bad Case 面试档案

## Bad Case 1：Ambiguous Transport 导致重复执行

**真实性：假设构造，已通过测试覆盖。**

触发：

```text
POST 已发送
→ LocalAgent 可能已经执行
→ response read reset
```

错误实现：

```text
标记 FAILURE
→ HTTP retry
```

风险：

```text
Tool 重复副作用
```

修复：

```text
OUTCOME_UNKNOWN
+
禁止 transport retry
```

知识点：

```text
Distributed Systems
Unknown Outcome
Idempotency
Retry Safety
```

------

## Bad Case 2：Timeout cleanup 覆盖根因

**真实性：假设构造，已通过测试覆盖。**

错误实现：

```text
Evaluation timeout
→ /cancel 成功
→ Outcome=CANCELLED
```

修复：

```text
root cause = EVALUATION_TIMEOUT
cleanup status = metadata only
```

知识点：

```text
Root Cause Preservation
Compensation
Cancellation Semantics
```

------

## Bad Case 3：Trace 丢失导致执行失败

**真实性：假设构造，已通过测试/静态验证覆盖。**

错误设计：

```text
没有 final Trace
→ execution failed
```

根因：

把：

```text
Observability
```

当成：

```text
Execution Authority
```

修复：

```text
structured terminal HTTP
= synchronous authority

Trace
= asynchronous evidence
```

------

## Bad Case 4：Evaluation timeout、HTTP timeout、Runtime timeout 相互竞争

**真实性：假设构造，已通过测试覆盖。**

修复：

```text
one outer deadline
↓
derive all subordinate budgets
```

知识点：

```text
Deadline Propagation
Timeout Ownership
Structured Concurrency
```

------

## Bad Case 5：LEGACY 模式偷偷执行

**真实性：假设风险，已通过 provider 测试覆盖。**

修复：

```text
/api/runtime/execute
→ COORDINATED-only
→ LEGACY fail closed
→ no fallback
```

目的：

保证 Baseline/Candidate 实际测试的是被冻结的 Runtime，而不是另一条 Legacy 路径。

------

# 25. 这个 WP 对系统设计能力的提升

完成这一 WP 后，你应该真正掌握的不只是 `httpx`。

而是：

```text
1. 系统边界如何通过 Adapter 隔离
2. Domain Owner 和 Protocol Adapter 如何分工
3. Deadline 怎么跨服务传播
4. Timeout / Cancellation 为什么不是同一件事
5. 分布式网络异常为什么会产生 Unknown Outcome
6. Retry 为什么依赖 Idempotency
7. Observability 为什么不能反向拥有业务状态
8. 如何保证 Baseline / Candidate 的实验变量控制
9. E2E 测试的真实性边界怎么表达
10. 如何用 Unit + Integration + E2E 组合证明架构
```

这实际上已经是一段非常不错的 **AI Agent + Backend + Distributed Systems（分布式系统）** 综合项目经历。

------

# 26. 最终记忆框架

面试前只需要记住这一条主线：

```text
为什么做？
Fixture Target 无法真实评估 LocalAgent。

怎么接？
ExecutionTarget → HTTP Adapter → structured LocalAgent endpoint。

为什么不用 /api/chat？
Streaming protocol 无可靠 terminal fact。

谁说 Run 成没成功？
RunCoordinator。

Trace 呢？
只做 Evidence，不做 execution authority。

timeout 怎么办？
Evaluation outer deadline → transport/runtime deadline propagation。

timeout 后为什么还 cancel？
清理远端资源，但 root outcome 仍是 TIMEOUT。

网络断了怎么办？
能证明没执行 → FAILURE。
可能执行了 → OUTCOME_UNKNOWN。

为什么不 retry？
没有 remote idempotency，怕重复副作用。

怎么验证？
Unit + PostgreSQL Integration + Cross-repo HTTP E2E + Runtime 组合证据。

真实性边界？
跨仓 HTTP 和 DB 是真实的；
live runtime 使用 deterministic fixture；
不能说成真实模型生产 E2E。
```

如果你把这条逻辑完整讲顺，`Stage5-Phase0-WP1` 就不再只是“给两个项目接了个 HTTP 接口”，而是一段非常完整的 **Evaluation Infrastructure（评估基础设施）+ Runtime Boundary（运行时边界）+ Distributed Failure Semantics（分布式故障语义）** 工程经历。