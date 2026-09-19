当前使用 GPT-5.6 Sol。

# Stage9-WP4 学习 / 面试总结

## Generic Durable Continuation + Lease / Reaper / Recovery

WP4 解决的核心问题一句话可以概括为：

> **Agent 任务进入等待或恢复阶段以后，Worker 挂掉不能让任务永久卡死，但“恢复调度”又绝不能被误做成“重新执行外部副作用”。**

最终形成的不是一套新的 Workflow Engine，而是一条明确的恢复链：

```text
READY
↓
Atomic Continuation Claim
↓
Payload Digest Verification
↓
Mandatory Run Lease / Fence
↓
WP3 ToolResolutionSnapshot Load / Validate / Hydrate
↓
Current Approval + Binding Recheck
↓
Existing DurableToolInvocation
↓
Existing Tool Execution Claim
↓
ToolExecutionService
↓
Transactional Business Writeback
↓
Claim Token + Run Fence Protected Terminal
```

Generic Continuation 只拥有恢复调度生命周期，Run、Approval、Tool Invocation、Execution Claim、业务状态仍然由各自原来的 Owner 管理。

Sol 最终把 Luna 第一版里 6 个 P1 和 1 个 P2 全部修掉，WP4 Final Gate 为 `PASS`，最终 `P0=0 / P1=0 / P2=0`。

------

# 1. WP4 到底补了什么

在 WP4 之前，其实已经有不少恢复相关组件：

```text
Run Lease / Fencing Token
Approval
Tool Execution Claim
Durable ToolInvocation
TicketContinuation
ToolResolutionSnapshot
```

问题是这些能力是分散的。

Stage8 的 TicketContinuation 能做到：

```text
READY
→ PROCESSING
→ SUCCEEDED
```

但它本质上还是 Ticket 业务专用。

而且第一版存在一个严重问题：

```text
PROCESSING
↓
Worker crash
↓
永远 PROCESSING
```

没有：

```text
Lease
Heartbeat
Reaper
```

所以 WP4 增加的是通用的：

> **Durable Continuation Scheduling Layer**

即：

```text
谁来恢复
什么时候可以接管
Worker 死了怎么重新变成 READY
旧 Worker 怎么失效
```

但它不负责：

```text
Tool 到底能不能执行
Provider 要不要 retry
Approval 是否有效
Run 是否归当前 Worker
```

------

# 2. 最重要的概念：Continuation Claim 不是 Execution Claim

这是整个 WP4 最应该记住的一句话。

假设：

```text
Worker A
```

拿到了：

```text
Continuation Claim
```

它只代表：

> Worker A 当前负责处理这个“恢复任务”。

不代表：

> Worker A 可以直接执行 Tool。

最终还要经过：

```text
Run Lease / Fence
↓
Approval
↓
ToolInvocation State
↓
Tool Execution Claim
↓
ToolExecutionService
```

所以：

```text
Continuation Claim
≠
Run Lease
≠
Tool Execution Claim
```

这三者解决三个不同问题：

```text
Continuation Claim
→ 谁负责恢复任务

Run Lease
→ 谁拥有当前 Run execution

Tool Execution Claim
→ 谁真正拥有某次 Tool side effect 的执行权
```

WP4 最终明确强制 Resume 必须取得 Run Lease，而不是把它做成“可选”。

------

# 3. 为什么需要 Lease

如果只有状态：

```text
READY
→ PROCESSING
```

那么 Worker Claim 后挂掉：

数据库只知道：

```text
PROCESSING
```

它不知道：

> Worker 还活着吗？

于是增加：

```text
claim_deadline_at
```

也就是租约（Lease）。

Claim 后：

```text
PROCESSING
claim_token = A
claim_deadline = 12:00:30
```

Worker 正常运行：

```text
Heartbeat
→ 延长 deadline
```

Worker 崩溃：

```text
Heartbeat 停止
↓
Lease expires
```

Reaper 才能安全回收。

------

# 4. 为什么还需要 Claim Token

Lease 解决：

> Worker 是否可能已经死了。

Claim Token 解决：

> 老 Worker 活过来了怎么办？

典型场景：

```text
Worker A
claim token=A

↓

A 卡住

↓

Lease expires

↓

Reaper → READY

↓

Worker B claim
token=B

↓

A 又恢复
```

如果没有 Token Fencing，A 可能：

```text
complete()
fail()
heartbeat()
```

覆盖 B 的状态。

所以现在所有 Worker mutation 都要求：

```text
continuation_id
+
current claim_token
```

旧 Token：

```text
A
```

在 B Claim 以后全部失效。

当前实现明确保证 stale worker 的 heartbeat、complete、fail 都被拒绝。

------

# 5. Claim Token 和 Run Fencing Token 为什么都需要

这是一个很好的面试追问。

Claim Token 防的是：

```text
旧 Continuation Worker
```

Run Fencing Token 防的是：

```text
旧 Run Executor
```

例如：

```text
Worker A
Continuation token A
Run fence 10
```

A 超时。

Worker B 接管：

```text
Continuation token B
Run fence 11
```

这时候 A 即使恢复：

它不仅 Continuation Token 失效，

它的：

```text
Run fence 10
```

也失效。

所以：

```text
Continuation state mutation
→ claim token fencing

Run/business mutation
→ Run fence
```

两层保护不能合并成一个。

------

# 6. Reaper 是干什么的

Reaper 只处理：

```text
PROCESSING
+
claim_deadline_at expired
```

它做的事情很简单：

```text
PROCESSING
→ READY
```

意味着：

> 这个恢复任务可以被其他 Worker 再次 Claim。

它不会：

```text
调用 Provider
执行 Tool
重跑 HTTP
重新创建 Ticket
```

也就是说：

> **Reaper 恢复的是 Scheduling，不是 Side Effect。**

这是 WP4 和很多“自动 retry”设计最关键的区别。

最终 Reaper 使用稳定排序和 `FOR UPDATE SKIP LOCKED`，并在最终更新时再次验证 state/token/deadline，避免与 Heartbeat 发生竞争。

------

# 7. Reaper Race 是什么

假设：

```text
12:00:30
Reaper 查到 A lease expired
```

就在它准备 UPDATE 时：

```text
Worker A heartbeat
→ deadline 延长到 12:01:00
```

如果 Reaper 只相信第一次查询：

就会错误：

```text
PROCESSING
→ READY
```

于是两个 Worker 都可能认为自己可以继续。

正确做法：

最终 UPDATE 时重新带条件：

```text
state = PROCESSING
AND token still current
AND deadline still expired
```

这也是为什么数据库 CAS / Row Lock 非常重要。

------

# 8. WAITING 和 READY 为什么不同

`WAITING`：

> 外部条件还没满足。

例如：

```text
Approval = PENDING
```

这时候 Worker 不应该不断 Claim。

`READY`：

> 恢复前提已经满足，可以被 Worker 调度。

例如：

```text
Approval = APPROVED
```

才可能：

```text
WAITING → READY
```

但是即使到了 READY：

Resume 时还必须重新检查 Durable Approval。

因为：

```text
READY
```

只是投影，

不是：

```text
Approval 永久有效
```

------

# 9. 为什么 Approval 在 Resume 时还要重新查

假设：

```text
12:00 Approval APPROVED
↓
Continuation READY
```

然后：

```text
12:01 Approval INVALIDATED
```

Worker 12:02 才 Claim。

如果 Worker 只看：

```text
Continuation READY
```

就会执行一个已经失效的 Approval。

所以 Resume 时必须重新读取：

```text
DurableApproval
```

并验证：

```text
status = APPROVED
approval_id
tool_invocation_id
invocation_binding_digest
```

WP4 最终已经强制这条链。

------

# 10. Payload Digest 是干什么的

Continuation 会保存：

```text
run_id
approval_id
tool_invocation_id
subject
resume reference
...
```

这些属于恢复 Contract。

如果创建 Continuation 时是：

```text
Payload A
```

之后数据库或调用者把它换成：

```text
Payload B
```

就可能变成：

```text
批准 A
恢复 B
```

所以保存：

```text
payload_digest
```

Resume 开始时重新计算。

不一致：

```text
FAILED
```

而不是：

```text
继续执行
```

------

# 11. 为什么恢复时必须加载 WP3 Snapshot

WP3 已经解决：

> 这个 Run 当初看到了哪些 Tool Contract。

WP4 不能把这个结果丢掉。

正确：

```text
Run resume
↓
load ToolResolutionSnapshot(run_id)
↓
validate
↓
hydrate
```

禁止：

```text
resume
↓
重新 Tool Discovery
```

否则 Run 暂停前后可能看到不同 Tool。

最终 Ticket Resume 已经强制使用 WP3 Snapshot；Snapshot 缺失、Schema Drift、Provider Drift、Descriptor Drift 都 fail closed。

------

# 12. 为什么 Snapshot Drift 不能 Requeue

比如：

```text
Snapshot expects Tool A schema v1
```

现在：

```text
Registry Tool A schema v2
```

如果：

```text
PROCESSING → READY
```

那么下一 Worker：

还是 v2。

再失败。

然后：

```text
READY → PROCESSING → READY
```

无限循环。

所以：

```text
Schema Drift
Provider Drift
Payload Digest Mismatch
Approval Binding Mismatch
```

这种属于：

> Permanent Resume Failure

应该：

```text
FAILED
```

不是 Requeue。

------

# 13. Retryable 和 Permanent Failure 怎么区分

可以这样理解。

## Retryable Scheduling Failure

例如：

```text
Worker crash
Lease expired
Temporary claim conflict
```

没有证明业务本身有问题。

可以：

```text
PROCESSING → READY
```

------

## Permanent Resume Failure

例如：

```text
Snapshot incompatible
Payload tampered
Approval invalid
Binding mismatch
```

换 Worker 也没用。

所以：

```text
FAILED
```

------

## Side-effect Ambiguity

例如：

```text
ToolInvocation = UNKNOWN
```

这是第三类。

它不能简单归到：

```text
Retryable
```

也不能说：

```text
FAILED 然后重试
```

它必须保持：

> UNKNOWN / explicit reconciliation

------

# 14. UNKNOWN 为什么是 WP4 最大安全点之一

场景：

```text
Tool provider
可能已经创建 Ticket
↓
HTTP timeout
↓
本地不知道结果
```

ToolInvocation：

```text
UNKNOWN
```

Worker 又 Crash。

Continuation Lease 过期。

Reaper：

```text
PROCESSING → READY
```

新的 Worker 接管。

这时候非常容易犯一个错误：

```text
READY
→ 再调用一次 create_ticket
```

可能创建两个 Ticket。

所以：

```text
Continuation requeue
≠ Tool retry
```

当前 WP4 明确：

```text
STARTED / UNKNOWN
→ 0 provider call
→ permanent failure / explicit reconciliation
```



------

# 15. COMMITTED 为什么也不能再调用 Provider

另一个场景：

```text
Ticket Platform
已经成功创建 Ticket

↓

ToolInvocation = COMMITTED

↓

Worker 在业务 writeback 前 crash
```

新 Worker 恢复。

错误：

```text
重新 create_ticket
```

正确：

```text
COMMITTED
↓
绝不再次 Provider call
```

然后看：

有没有：

```text
durable provider result
```

如果有：

做安全 writeback。

如果没有：

进入：

```text
TOOL_INVOCATION_COMMITTED_REPAIR_REQUIRED
```

而不是冒险重复副作用。

------

# 16. 当前 COMMITTED 的一个真实限制

当前 ToolInvocation Schema：

在某些情况下：

```text
COMMITTED
```

并没有保存足够的 Provider Result Payload，让新的 Worker 可以自动重建 Ticket business writeback。

所以现在选择：

```text
explicit/manual repair
```

而不是：

```text
重新调用 Provider
```

这是很典型的生产取舍：

> 宁可留下可观察、可修复的中间状态，也不能为了“自动恢复”重复非幂等副作用。

这是当前明确 Known Limitation。

------

# 17. TicketContinuation 怎么被统一

Stage8 原来有：

```text
TicketContinuation
```

它同时包含：

```text
业务数据
+
调度 claim
```

WP4 后拆开：

```text
Stage8 TicketContinuation
=
Ticket business projection
```

而：

```text
runtime_continuations
=
Scheduling Claim / Lease / Attempt / Terminal Truth
```

旧的：

```text
claim_ticket_continuation()
```

已经删除。

现在：

```text
process_ready_once()
↓
Generic Claim
↓
Generic Resume
↓
Ticket Handler
```

因此没有两套 Claim Authority。

------

# 18. Generic Continuation 为什么不是 Workflow Engine

虽然现在已经有：

```text
WAITING
READY
PROCESSING
SUCCEEDED
FAILED
CANCELLED
```

但它仍然不是 Temporal。

因为它不拥有：

```text
业务 DAG
复杂 Timer
Signal
Compensation
Workflow DSL
Activity retry policy
```

它解决的是：

> Durable Resume Scheduling。

业务状态还是由：

```text
Mission
Ticket
Run
ToolInvocation
```

自己的 Domain Owner 管理。

所以不能说：

> 我实现了 Temporal。

更准确：

> 我实现了一个最小 Durable Continuation Scheduling Layer，解决 Worker crash 后的可恢复调度和 fencing，复杂 Workflow Engine 仍然是 Non-goal。

------

# 19. State Machine

最终：

```text
WAITING
↓
READY
↓
PROCESSING
├→ SUCCEEDED
├→ FAILED
└→ CANCELLED
```

特殊路径：

```text
PROCESSING
↓ lease expired
READY
```

并且只有：

```text
Reaper
```

可以做：

```text
PROCESSING → READY
```

Terminal：

```text
SUCCEEDED
FAILED
CANCELLED
```

不能互相覆盖。

------

# 20. Run Cancel 如何影响 Continuation

如果：

```text
Continuation READY
```

但：

```text
Run already cancelled
```

Worker Resume 后不能继续：

```text
ToolExecution
```

而是：

```text
Generic Continuation → CANCELLED
```

所以 Explicit Run Cancel 的 Durable Truth 仍然有效。

Continuation 不会把它覆盖。

------

# 21. Cross-worker Recovery 怎么工作

真实模型：

```text
Worker A
↓
claim continuation
↓
PROCESSING
↓
claim deadline
```

A Crash。

数据库仍然：

```text
PROCESSING
deadline expired
```

Worker B：

```text
Reaper
↓
READY
↓
claim token B
↓
new Run fence
↓
resume
```

整个过程只依赖 PostgreSQL。

不依赖：

```text
Worker A memory
asyncio task
local queue
```

最终 focused test 已经真实覆盖 A/B Worker takeover。

------

# 22. Crash Recovery Matrix

当前可以记住这六个状态：

| Crash 点              | 恢复                                            |
| --------------------- | ----------------------------------------------- |
| Continuation Claim 前 | 仍然 READY                                      |
| Claim 后 Worker Crash | Lease → Reaper → READY                          |
| Run Lease 后 Crash    | 新 Worker 获取更高 Fence                        |
| Tool 调用前 Crash     | 恢复原 Approval / Invocation / Claim            |
| Provider 状态模糊     | UNKNOWN，不自动 Retry                           |
| Tool 已 COMMITTED     | 不重复 Provider Call，只处理 Writeback / Repair |

这也是整个 WP4 最核心的故障模型。

------

# 23. Owner / Truth / Authority

面试最好能讲清下面这张表：

| 事实 / 权限                       | Owner                                    |
| --------------------------------- | ---------------------------------------- |
| Continuation 调度                 | GenericContinuationService / PostgreSQL  |
| 当前 Worker 是否拥有 Continuation | Claim Token + Lease                      |
| 当前谁拥有 Run                    | DurableRunControlService + Fencing Token |
| Tool Contract                     | WP3 ToolResolutionSnapshot               |
| Approval 当前状态                 | DurableApprovalService                   |
| ToolInvocation Side-effect State  | DurableToolInvocationService             |
| Tool 执行权                       | Tool Execution Claim                     |
| 实际 Provider 调用                | ToolExecutionService                     |
| Ticket 业务状态                   | Ticket Domain Service                    |

最核心原则：

> **可以有多层 Claim，但每一层必须只回答一个问题。**

------

# 24. 名词 / 概念速览

持久化续跑（Durable Continuation）：把“以后继续执行”本身作为数据库中的持久化调度任务。

租约（Lease）：给 Worker 一个有过期时间的临时处理权。

心跳（Heartbeat）：Worker 还活着时延长 Lease。

回收器（Reaper）：发现 Lease 已过期的 PROCESSING Continuation，并重新变成 READY。

申领令牌（Claim Token）：区分新旧 Worker Claim，防止旧 Worker 恢复后继续修改状态。

隔离令牌（Fencing Token）：Run takeover 后递增，用来阻止旧 Run Owner 继续写状态。

恢复（Resume）：从 Durable Identity 和 Durable State 重建执行上下文，而不是从内存继续。

对账（Reconciliation）：对于 UNKNOWN 这类无法确定副作用是否发生的状态，通过外部查询等方式确认，而不是 blind retry。

------

# 25. 真实 Bad Case 1：Run Lease 原来是可选

### REAL

Luna 第一版：

```text
resume_claimed(
    run_control_service = optional
)
```

这意味着 handler 理论上可以：

```text
Continuation Claim
↓
直接恢复业务
```

不拿 Run Lease。

Sol 判为 P1。

最终：

```text
所有绑定 Run 的 Resume
→ mandatory Run Lease / Fence
```



------

# 26. 真实 Bad Case 2：Ticket Resume 绕过 Generic Resume

### REAL

第一版：

```text
Ticket process_ready_once()
→ resume_approved()
```

直接走 Ticket Handler。

Generic Continuation 只创建了记录，却没有成为真正恢复入口。

最终修成：

```text
Generic Claim
↓
Generic Resume
↓
Ticket Handler
```

同时删除旧：

```text
claim_ticket_continuation()
```

避免第二 Claim Authority。

------

# 27. 真实 Bad Case 3：恢复时没有 Snapshot

### REAL

第一版 Stage8 Ticket 首次 Approval 路径：

没有创建 WP3 Tool Snapshot。

恢复：

```text
current Registry
→ Tool registration
```

这实际上重新使用了当前 Tool Contract。

最终修成：

```text
首次进入 approval-required path
↓
create ToolResolutionSnapshot

Resume
↓
load + validate + hydrate
```

不再 Rediscovery。

------

# 28. 真实 Bad Case 4：COMMITTED / UNKNOWN 只靠底层间接挡

### REAL

第一版虽然 Tool Runtime 本身有 UNKNOWN Safety Contract，

但 Ticket Resume Path 没有显式读取：

```text
Durable ToolInvocation State
```

所以 Continuation 层无法证明不会重试。

最终增加：

```text
read invocation state

STARTED / UNKNOWN
→ no provider call

COMMITTED
→ no provider call
```

这就是：

> Owner 不变，但调用链必须真实交回 Owner。

------

# 29. 工程构建类面试问题：为什么需要 Generic Continuation

可以回答：

> 我原来 Stage8 有一个 TicketContinuation，但它是业务专用，而且 Worker 进入 PROCESSING 后如果崩溃会永久卡住。后来我把调度部分抽成 Generic Durable Continuation，状态和 Claim 存 PostgreSQL，PROCESSING 有 Lease 和 Heartbeat，Worker 崩溃后 Reaper 可以重新变成 READY。它只负责恢复调度，真正恢复 Run 时还必须重新取得 Run Lease、加载 Tool Snapshot、检查 Approval 和 ToolInvocation，不能把 Continuation Claim 当执行权。

------

# 30. 面试题：为什么不用 Redis 存 Continuation

回答：

> 因为 Continuation 是业务恢复事实，进程或 Redis 故障后不能丢。我的 durable truth 放在 PostgreSQL，Claim、Lease、状态迁移也在数据库做 CAS/锁。Redis 或 Kafka以后可以做 wake-up，但不能成为 Continuation Truth。

------

# 31. 面试题：为什么 PROCESSING 还要 Lease

回答：

> PROCESSING 本身不能证明 Worker 还活着。如果 Worker Claim 后崩溃，没有 Lease 就会永久卡死。现在 PROCESSING 会绑定 claim deadline，Worker 用 heartbeat 续租，过期后 Reaper 只把它重新变成 READY，允许其他 Worker 接管。

------

# 32. 面试题：为什么 Reaper 不能直接 Resume

回答：

> 因为 Reaper 只知道 Worker Lease 过期，不知道业务副作用执行到了哪一步。尤其 Tool 可能已经到 Provider，只是响应丢了。所以 Reaper 只恢复 scheduling，把 PROCESSING 变回 READY，真正 Resume 还要重新读取 ToolInvocation，UNKNOWN 就绝不能 blind retry。

------

# 33. 面试题：两个 Worker 同时恢复怎么办

回答：

> Continuation 层先通过 PostgreSQL 原子 Claim 保证同一个 READY 只有一个 Worker 进入 PROCESSING，每次生成新的 claim token。即使旧 Worker 后来恢复，它的 token 已经过期。同时 Run 还有单独的 Lease 和 fencing token，所以新 Worker接管以后，旧 Worker既不能改 Continuation，也不能提交新的 Run mutation。

------

# 34. 面试题：为什么有 Claim Token 还需要 Run Fence

回答：

> 因为它们保护不同资源。Claim Token 保护的是 Continuation scheduling state，Run Fence 保护的是 Run execution truth。如果 Worker 已经拿到 Continuation，但没有 Run ownership，仍然不能修改 Run 或继续 Tool 链。所以 Resume 时两层都必须验证。

------

# 35. 面试题：Worker Crash 以后 Tool 会不会执行两次

回答：

> Continuation 本身不会决定重试 Tool。恢复时先读取原 DurableToolInvocation。如果是 PREPARED，才可能继续走原有 Execution Claim；如果是 STARTED 或 UNKNOWN，不会调用 Provider；如果已经 COMMITTED，也不会再调用 Provider，只处理已有结果的 writeback，或者进入明确 repair 状态。

------

# 36. 面试题：为什么 COMMITTED 还可能需要人工修复

回答：

> 因为当前有些 ToolInvocation 只持久化了 COMMITTED 状态，没有持久化完整可重放的 Provider Result。这样 Worker 如果恰好在 Provider 成功后、业务 writeback 前崩溃，我能证明不能重复 Provider 副作用，但不一定有足够数据自动补业务写回。所以我选择显式 repair，而不是为了自动恢复冒险重复副作用。

这个回答比较有工程可信度。

------

# 37. 面试题：这是不是自己实现 Temporal

回答：

> 不是。我这里只实现了一个最小 Durable Continuation Scheduling Layer，解决 READY/PROCESSING、Lease、Heartbeat、Reaper 和 Worker takeover。业务 Workflow、Timer、Signal、Compensation、Activity Retry 这些并没有实现。如果以后长期 Workflow 复杂到这个程度，我会评估 Temporal，而不是继续无限扩自己的 Continuation 层。

------

# 38. 如果真实面试再次问到

## 问：Agent 任务触发审批以后，HTTP 请求结束了，怎么继续？

### WP4 完成前

可以回答：

> 我会把等待状态持久化，审批后重新触发一个 Worker 恢复执行。

但这更多还是设计。

### WP4 完成后

现在可以回答：

> “我现在把这种恢复做成了 Durable Continuation。进入等待点以后，Continuation 和恢复所需的 durable reference 存 PostgreSQL；条件满足后变 READY，Worker 通过原子 Claim 进入 PROCESSING，同时拿一个带期限的 Claim Token。Resume 时还必须重新获取 Run Lease/Fence、加载原 Tool Snapshot、检查当前 Approval 和 ToolInvocation。Worker 如果挂了，Lease 到期后 Reaper 只把调度状态恢复成 READY，不会直接重试 Tool。新的 Worker接管以后，旧 Worker同时被 Claim Token 和 Run Fence 挡住。”

------

# 39. 如果再次被问“服务重启怎么办”

### WP4 前

原来只能说：

```text
Run / Approval / Tool State
在 PostgreSQL
```

但 Continuation 本身仍有缺口。

### WP4 后

可以回答：

> “恢复任务本身现在也是 PostgreSQL Durable State。Claim owner、token、lease deadline 都持久化，所以新实例不需要旧进程内存。它可以 Reap 过期 PROCESSING、重新 Claim，然后通过 Run Fence、Tool Snapshot 和 Approval/ToolInvocation 状态恢复执行。”

------

# 40. Known Limitations

当前仍没有：

```text
long-running scheduler daemon
Kafka wake-up
automatic UNKNOWN reconciliation
Temporal-style generic workflow DSL
generic compensation
```

同时 COMMITTED 但业务 writeback 尚未完成，如果缺少 durable Provider Result Payload：

```text
explicit repair
```

仍然是当前限制。

这些都是当前源码明确承认的边界。

------

# 41. WP4 最需要记住的 8 句话

1. **Continuation Claim 只解决谁负责恢复，不代表谁可以执行副作用。**
2. **PROCESSING 没有 Lease，就可能因为 Worker Crash 永久卡死。**
3. **Claim Token 防旧 Continuation Worker，Run Fence 防旧 Run Owner。**
4. **Reaper 只恢复 Scheduling，绝不能直接重试业务。**
5. **Resume 必须使用 WP3 原 Snapshot，不能重新 Discovery。**
6. **Approval READY 只是投影，Resume 时必须重新查 Durable Approval。**
7. **UNKNOWN 和 STARTED 绝不能因为 Worker 换了就重新调用 Provider。**
8. **COMMITTED 只能做安全 Writeback / Repair，不能再产生同一外部副作用。**

推荐学习文件名：

```text
stage9_wp4_durable_continuation_lease_reaper_recovery_learning.md
```

WP4 学习完成。下一步按照 Stage9 原始路线进入 **Stage9-WP5 — Capacity Model + Load Evidence + SLO**。