当前使用 GPT-5.6 Sol。

# Stage9 总学习 / 面试总结

## Runtime Platform Hardening & Resumability

Stage9 最终完成状态：

```text
STAGE9_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

BLOCKING_P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0
ACCEPTED_P2 = 4

ARCHITECTURE_REOPEN_REQUIRED = NO
READY_TO_CLOSE_STAGE9 = YES
```

Stage9 的 Frozen Scope 已经闭环。最终保留的都是明确的非阻断限制，而不是没有做完的核心 Contract。

推荐总学习文档文件名：

```text
stage9_runtime_platform_hardening_resumability_learning.md
```

------

# 一、Stage9 到底解决了什么

Stage9 之前，AgentCore 已经不是一个简单的 Agent Demo。

前面的 Stage 已经有：

```text
Run 生命周期
并发调度
Tool Runtime
Typed Validation
Governance
HITL
Approval
Execution Claim
Side-effect Ledger
MCP
PostgreSQL Journal
Streaming
Recovery 基础
```

但真实面试暴露出来的问题是：

> **这些能力单独存在，不代表已经组成了一个真正可恢复、可跨实例、可证明容量边界的 Runtime Platform。**

Stage9 因此不是继续堆 Agent Feature，而是在补 Runtime Platform 的几个关键基础设施问题：

```text
对象授权
↓
连接与 Run 生命周期解耦
↓
可恢复 Streaming
↓
Tool Contract 稳定性
↓
Worker Crash 后的 Durable Resume
↓
真实容量和 SLO Evidence
```

最终形成的生产链已经是：

```text
JWT verification / DB tenant binding
→ Principal
→ ObjectAuthorizationService
→ /api/v1 Run Admission
→ Run / Conversation Ownership
→ PostgreSQL ToolResolutionSnapshot
→ Deterministic Tool Discovery
→ Snapshot-only Tool Resolution
→ Typed Validation
→ ToolGovernanceService
→ Durable Approval
→ runtime_continuations
→ Continuation Claim / Lease
→ Run Lease / Fencing Token
→ Snapshot Load / Validate / Hydrate
→ Approval + Binding Recheck
→ Tool Execution Claim
→ ToolExecutionService
→ DurableToolInvocation
→ Runtime Journal + Client Feed
→ PostgreSQL SSE Replay
→ RUN_COMPLETED
```



这条链是 Stage9 最值得整体记住的东西。

------

# 二、Stage9 的核心变化

Stage9 可以概括成六个 WP。

| WP   | 核心问题                                                     | 最终结果                                      |
| ---- | ------------------------------------------------------------ | --------------------------------------------- |
| WP0  | Runtime 的 Owner / Truth / Resume Contract 不够明确          | 冻结 Stage9 Contract                          |
| WP1  | 有 JWT 不等于有对象级授权                                    | Tenant-first Object Authorization + `/api/v1` |
| WP2  | HTTP/SSE 断开会影响 Run，无法跨实例 Resume                   | PostgreSQL Client Feed + Resumable SSE        |
| WP3  | Tool 多了以后上下文膨胀，Run 恢复时 Tool Contract 会漂移     | Top-K Discovery + Durable Tool Snapshot       |
| WP4  | PROCESSING Worker Crash 后可能永久卡死，恢复又可能误重试副作用 | Durable Continuation + Lease/Reaper/Fence     |
| WP5  | “有并发控制”不等于“有容量证据”                               | Capacity Model + Runtime Load + Candidate SLO |

最终 Completion Matrix 中这些能力均已经实现并经过对应测试。

------

# 三、WP0 — 为什么先做 Contract Freeze

WP0 没有追求功能。

它主要解决：

> **后面的恢复、授权、Streaming、Tool Snapshot 到底谁拥有 Truth。**

这是很重要的一步。

因为如果不先冻结 Owner，很容易出现：

```text
Client Feed 变成 Runtime Truth
Continuation Claim 变成 Run Ownership
Snapshot 变成 Tool Authorization
Redis 变成恢复 Truth
MCP 变成 Execution Authority
```

Stage9 最终一直保持的几个原则是：

```text
PostgreSQL
= Durable Truth

process memory
= optimization

Client Connection
!= Run Lifecycle

Continuation Claim
!= Run Lease

Run Lease
!= Tool Execution Claim

Tool Snapshot
!= Tool Registry

Tool Snapshot
!= Authorization

Discovery
!= Governance

Approval
!= Execution Claim
```

这其实就是整个 Stage9 的 Architecture Backbone。

------

# 四、WP1 — Authentication 不等于 Authorization

很多项目会做到：

```text
JWT 验证成功
→ 用户登录了
```

然后就认为：

```text
可以访问 run_id
approval_id
job_id
```

这是不够的。

Stage9 WP1 把对象授权明确抽成：

```text
ObjectAuthorizationService
```

最小身份模型：

```text
tenant_id
owner_user_id
roles
scopes
principal kind
```

主要规则：

```text
HUMAN
→ same tenant + owner

ADMIN
→ tenant-local admin
→ 不是全局管理员

SERVICE
→ same tenant
+ exact scope
+ action policy
```

对象动作至少包含：

```text
READ
MUTATE
CANCEL
APPROVE
PROCESS
RESUME
SUBSCRIBE
```

Final Gate 再次确认：

```text
CROSS_TENANT_ACCESS = NO
OBJECT_AUTH_BYPASS = NO
SUBSCRIBE_BYPASS = NO
```



------

# 五、为什么跨 Tenant 返回 404 而不是 403

这是一个很常见的安全设计问题。

如果：

```text
GET /runs/run-A
```

当前用户没有权限，而系统返回：

```text
403
```

就等于告诉攻击者：

> run-A 这个对象存在。

Stage9 的 Public Object Semantics 更偏向：

```text
对象不存在
或
对象不属于当前 Tenant
```

统一：

```text
404
```

这样降低 Object Enumeration。

------

# 六、WP2 — Connection Lifetime 和 Run Lifecycle 为什么要拆开

这是 Stage9 最核心的 Runtime 改造之一。

错误模型：

```text
HTTP connection exists
= Run exists

HTTP disconnect
= Cancel Run
```

这种模式对简单聊天可以工作。

但一旦进入：

```text
长任务
审批
移动端网络抖动
反向代理重连
实例重启
SSE reconnect
```

就不成立了。

Stage9 冻结的新语义：

```text
/api/v1 disconnect
→ subscription ends

Run
→ continues
```

如果用户真的想停止：

```text
Explicit Cancel
```

才是独立 Durable Command。

Final Gate 已确认：

```text
CLIENT_DISCONNECT_RUN_CANCEL_V1 = NO
```



------

# 七、为什么不能直接 Replay Runtime Journal

Runtime Journal 是内部执行事实。

里面可能包含：

```text
内部状态
Tool 参数
risk facts
provider error
private path
memory context
内部 Runtime object
```

这些都不应该直接暴露给 Client。

所以 WP2 引入：

```text
Client Delivery Feed
```

形成：

```text
Runtime Journal
↓
Client-safe Projection
↓
client_delivery_events
↓
SSE
```

最终允许暴露的事件主要是：

```text
RUN_STARTED
OUTPUT_DELTA
ERROR
CANCELLATION
TOOL_APPROVAL_REQUESTED
RUN_COMPLETED
```

而 raw Tool args、secret、stacktrace、private memory 等明确不会进入 Client Feed。

------

# 八、Resumable SSE 是怎么做的

核心设计：

```text
PostgreSQL Client Feed
+
Monotonic Cursor
+
Last-Event-ID
```

语义：

```text
delivery = AT_LEAST_ONCE

dedup key
= (run_id, cursor)

Last-Event-ID
= exclusive cursor
```

例如 Client 收到：

```text
cursor = 23
```

断开以后：

```text
Last-Event-ID: 23
```

服务端查询：

```text
cursor > 23
```

继续发送。

所以跨实例恢复不需要：

```text
旧 Worker
旧 websocket
旧 asyncio Queue
```

只需要 PostgreSQL。

Final Gate 明确确认：

```text
CROSS_INSTANCE_REPLAY = SUPPORTED_BY_POSTGRESQL
```



------

# 九、为什么是 At-least-once，而不是 Exactly-once

网络 Delivery 的 exactly-once 成本很高，而且通常没有必要。

当前选择：

```text
at-least-once delivery
+
stable cursor
+
client dedup
```

更合理。

真正要求 Exactly-once / Single Winner 的地方，是：

```text
Tool Execution Claim
Continuation Claim
Approval CAS
```

不是网络层。

这也是面试中很容易被混淆的一点。

------

# 十、Journal + Client Feed 为什么要原子写

一个危险窗口：

```text
Runtime Journal COMMITTED
↓
process crash
↓
Client Feed 没写
```

那么 Runtime 自己知道已经完成，

Client 永远不知道。

所以正常事件：

```text
Journal
+
Client Feed projection
```

在同一 transaction。

Terminal 更严格：

```text
Run Fence Check
+
Journal Terminal
+
Client Feed Terminal
+
Run Control Close
```

同一 durable boundary。

Final Gate 再次确认这条 Contract 没有被后续 WP 破坏。

------

# 十一、WP3 — Tool 多了以后为什么需要 Discovery

如果系统只有：

```text
5 个 Tool
```

全塞给模型问题不大。

如果以后：

```text
100
500
1000 tools
```

还把所有：

```text
name
description
JSON Schema
```

放 Prompt：

会产生：

```text
Context 膨胀
Tool selection noise
无关 Schema 干扰
成本上升
```

所以加入：

```text
Deterministic Tool Discovery
→ Top-K
```

当前实现是：

```text
metadata keyword matching
+
stable ranking
+
stable tie-break
```

不是 Embedding Retriever。

这点面试一定要真实讲。

------

# 十二、为什么 Discovery 不是 Authorization

Discovery 回答：

> 哪些 Tool 值得让模型看到？

Authorization / Governance 回答：

> 当前这次具体调用能不能执行？

例如：

```text
delete_file
```

可能因为任务和文件有关进入 Top-K。

但真正执行还必须检查：

```text
Principal
Resource
Arguments
Side Effect
Risk
Approval
```

所以：

```text
Discovery Filter
!= Final Authorization
```

这是 WP3 很重要的架构边界。

------

# 十三、为什么还需要 Tool Snapshot

只有 Discovery 还不够。

场景：

```text
Run starts
Tool A schema = v1

↓

Run waits for approval

↓

deploy

↓

Tool A schema = v2

↓

Run resumes
```

如果直接读取最新 Registry：

同一个 Run：

```text
前半段 → v1
后半段 → v2
```

Tool Contract 漂移了。

所以 WP3 加了：

```text
ToolResolutionSnapshot
```

并且必须：

```text
PostgreSQL durable
```

而不是只存在 `RunContext` 内存里。

Final Gate 确认：

```text
DURABLE_TOOL_SNAPSHOT = SUPPORTED
```



------

# 十四、Snapshot 保存什么

核心包括：

```text
selected tool identity
schema digest
descriptor digest
registry digest
provider identity
MCP identity
selection algorithm version
snapshot schema version
selection evidence digest
```

它保存：

> Contract Identity

不保存：

```text
Python callable
Adapter instance
MCP session object
```

恢复时：

```text
snapshot
↓
current registry lookup
↓
identity / schema validation
↓
hydrate runtime object
```

------

# 十五、Snapshot Drift 怎么处理

旧 Run 恢复时：

```text
new Tool added
→ invisible

selected Tool removed
→ block

schema changed
→ block

provider changed
→ block

descriptor changed
→ block

permission revoked
→ current Governance deny

permission expanded
→ old snapshot 不扩张
```

关键思想：

> **Resume 的目标是恢复旧 Contract，而不是偷偷升级到最新 Contract。**

Final Gate 明确：

```text
RESUME_REDISCOVERY = NO
SNAPSHOT_DRIFT_SILENT_ACCEPT = NO
```



------

# 十六、为什么 MCP session_generation 不能当 Durable Identity

MCP reconnect 后：

```text
session_generation
```

可能变化。

甚至 process restart 后重新从头计数。

所以它只是：

```text
runtime evidence
```

不能作为：

```text
durable identity
```

真正需要的是：

```text
server/provider identity
remote tool identity
schema digest
```

这才能跨进程比较。

------

# 十七、WP4 — Durable Continuation 到底是什么

它不是：

```text
Temporal
```

也不是完整 Workflow Engine。

它只是：

> **一个 Durable Resume Scheduling Layer。**

状态：

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

它解决：

```text
谁负责恢复
Worker Crash 后谁接管
旧 Worker 怎么失效
什么时候可以再次调度
```

不解决：

```text
Tool 能不能执行
Approval 是否有效
Run 谁拥有
Provider 要不要 retry
```

------

# 十八、Continuation Claim、Run Lease、Tool Claim 的区别

这是 Stage9 最重要的 Owner 问题之一。

### Continuation Claim

回答：

> 谁负责处理这个 Resume Task？

### Run Lease

回答：

> 谁拥有当前 Run execution？

### Tool Execution Claim

回答：

> 谁拥有这一次具体 Tool Side Effect 的执行权？

所以：

```text
Continuation Claim
!= Run Lease
!= Tool Execution Claim
```

Final Gate Owner Matrix 也确认这些 Owner 仍然独立。

------

# 十九、为什么需要 Lease + Heartbeat + Reaper

没有 Lease：

```text
READY
→ PROCESSING
→ Worker Crash
```

数据库会永久：

```text
PROCESSING
```

所以加：

```text
claim_deadline_at
```

Worker 正常工作：

```text
Heartbeat
→ renew lease
```

Worker Crash：

```text
lease expires
↓
Reaper
↓
PROCESSING → READY
```

但是 Reaper：

> **只恢复 Scheduling。**

不能：

```text
直接 Resume
直接调用 Provider
直接 retry Tool
```

------

# 二十、为什么还要 Claim Token

Worker A：

```text
claim token = A
```

卡住。

Lease 过期。

Worker B：

```text
claim token = B
```

这时 A 又恢复。

如果没有 Claim Token：

A 还能：

```text
complete
fail
heartbeat
```

覆盖 B。

所以 Worker mutation 必须绑定：

```text
continuation_id
+
current claim_token
```

旧 token 一律拒绝。

------

# 二十一、为什么 Claim Token 仍然不能替代 Run Fence

因为 Claim Token 保护：

```text
Continuation scheduling state
```

Run Fence 保护：

```text
Run state
```

场景：

```text
Worker A
claim=A
run fence=10

Worker B takeover
claim=B
run fence=11
```

A 醒来以后：

```text
Continuation mutation
→ token A fails

Run mutation
→ fence 10 fails
```

两层都需要。

------

# 二十二、WP4 最重要的安全语义：Recovery != Retry

Worker Crash 后：

```text
Continuation
PROCESSING → READY
```

这不意味着：

```text
Tool call again
```

新的 Worker Resume 时首先读取：

```text
DurableToolInvocation
```

根据状态决定。

------

# 二十三、PREPARED / STARTED / UNKNOWN / COMMITTED 怎么恢复

### PREPARED

副作用还没确定执行：

```text
可以继续走 existing Tool Claim
```

### STARTED / UNKNOWN

Provider 可能已经收到请求。

所以：

```text
0 Provider retry
```

### COMMITTED

Provider 已经成功：

```text
0 duplicate Provider call
```

如果有 Durable Result：

```text
继续 writeback
```

如果没有足够 Result：

```text
explicit/manual repair
```

绝不能为了“自动恢复”重复 Side Effect。

Final Gate 明确：

```text
UNKNOWN_RETRY_RISK = NO
```



------

# 二十四、为什么 UNKNOWN 不 Blind Retry

最典型的情况：

```text
create_ticket()
↓
远端已经成功创建
↓
Response lost
↓
本地 timeout
```

本地不知道有没有成功。

如果自动重试：

可能：

```text
创建两个 Ticket
```

所以：

```text
UNKNOWN
→ stop
→ reconcile / repair
```

这比“自动恢复一切”更生产化。

------

# 二十五、TicketContinuation 为什么还保留

Stage8 已经有：

```text
TicketContinuation
```

WP4 没有直接删掉。

而是拆 Owner：

```text
TicketContinuation
= business projection / facade

runtime_continuations
= scheduling truth
```

旧的独立：

```text
claim_ticket_continuation()
```

已经移除。

所以：

```text
business state
```

可以保留，

但：

```text
scheduling authority
```

只有一份。

------

# 二十六、WP5 — 为什么一定要做真实 Load Evidence

“系统用了 Semaphore、Pool、Async”不代表：

> 系统有容量证据。

Luna 第一版其实已经跑出了很漂亮的数据：

```text
synthetic endpoint
c=1/5/10/25
0 errors
```

但没有：

```text
PostgreSQL
Run lifecycle
SSE
Continuation
```

所以 Sol 明确判定：

> Synthetic-only evidence 不足以满足 WP5。

后来才补：

```text
REAL PLATFORM_RUNTIME
```

------

# 二十七、WP5 最重要的真实 Bad Case：Active Runs 无界

修复前：

```text
c=5
100 Runs quickly accepted
```

结果：

```text
90s 后
44 Runs 无 durable terminal
```

Root Cause：

```text
Active Runs unbounded
```

API 接得太快，

Runtime 实际执行能力跟不上。

这属于典型：

> **Hidden Backlog。**

------

# 二十八、怎么修的

最终：

```text
RunExecutionSupervisor
→ 4 active producer slots
```

而且：

```text
Admission
```

发生在：

```text
Durable Run Binding
```

之前。

因此过载行为变成：

```text
wait for slot
↓
start latency increases
↓
Run accepted
↓
Run completes
```

而不是：

```text
accept immediately
↓
hidden backlog
↓
terminal missing
```

这是非常典型的 Backpressure 设计。

------

# 二十九、为什么 Backpressure 比“先接受再说”好

一个请求：

```text
accepted
```

对于客户端通常意味着：

> 系统已经可靠接管。

如果其实只是：

```text
把任务塞进内存
```

而没有 capacity，

系统就把容量风险藏起来了。

Backpressure 应该让压力变成：

```text
latency
queue
rejection
```

这种调用方可观察信号。

------

# 三十、真实 Runtime Capacity 结果

当前测试环境：

```text
single local machine
single uvicorn worker
local PostgreSQL
scripted backend
remote provider excluded
```



Run Start：

| 并发 | p95    | Throughput |
| ---- | ------ | ---------- |
| 1    | 136ms  | 11.46 RPS  |
| 5    | 697ms  | 11.53 RPS  |
| 10   | 1085ms | 11.37 RPS  |
| 25   | 2704ms | 11.05 RPS  |

同时：

```text
Run Start Loss = 0
Run ID Collision = 0
Ownership Error = 0
```



------

# 三十一、怎么解释这组数据

吞吐：

```text
≈ 11 RPS
```

基本没涨。

但 latency：

```text
136ms
→ 697ms
→ 1085ms
→ 2704ms
```

说明：

```text
4 active producer slots
```

已经成为 Admission Bound。

更高并发主要在排队，

不是增加并行执行数量。

所以：

```text
performance saturation = YES at c25
correctness saturation = NO
```



------

# 三十二、为什么 c25 SLO FAIL 还能 Stage9 PASS

Candidate SLO：

```text
Runtime Run Start p95 <= 2000ms
```

实际：

```text
c25 p95 = 2704ms
```

所以：

```text
FAIL
```

而不是事后改成：

```text
<=3000ms
```

Final Gate 仍然保留这个 FAIL。

因为 Stage9 的目标是：

> 建立可信 Evidence。

不是：

> 把所有数字都调成绿色。

所以：

```text
Stage9 implementation = PASS

Candidate SLO at c25 = FAIL
```

完全可以同时成立。

------

# 三十三、SSE Load Evidence

真实 Replay：

```text
c=1/5/10/25
每档 100 samples
```

结果：

```text
replay gap = 0
logical duplicate = 0
terminal loss = 0
```

Disconnect / Resume：

```text
20/20
accidental Run cancellation = 0
```



所以现在可以说：

> Resumable Streaming 不只是设计或单元测试，已经有 PostgreSQL-backed Runtime load evidence。

------

# 三十四、Continuation Load Evidence

真实测试：

```text
c=1/5/10/25
100 continuations each
```

结果：

```text
duplicate claim = 0
remaining READY = 0
```

同时：

```text
expired PROCESSING
→ reap/reclaim

stale worker mutation
→ rejected
```



但一定要注意：

> 这证明的是 Scheduling Claim Single Winner。

不是：

> 外部 Provider Exactly-once。

------

# 三十五、Stage9 还真实发现了 Event Loop Blocking Bug

原来：

```text
BoundedBlockingExecutor.submit()
```

会在 Event Loop 上同步等待 admission。

当 executor 满：

```text
Event Loop
↓
blocking admission
```

可能造成：

```text
starvation / deadlock risk
```

最终把 admission 移到：

```text
asyncio.to_thread
```

然后：

```text
result_async()
```

回异步链。

这是非常值得面试讲的真实生产 Bug。

------

# 三十六、Final Gate 又发现了一个 P0：SLO False PASS

原来的 Evaluator 对缺失：

```text
latency
error_rate
success_rate
```

部分字段使用默认值。

例如：

```text
missing latency
→ 0
```

那么：

```text
0 <= 2000
→ PASS
```

这属于严重 Evidence Bug。

Final Gate 修成：

```text
missing required metric
→ NOT_ENOUGH_EVIDENCE
```

而不是 PASS。

这被定为 P0。

------

# 三十七、为什么“错误证据 PASS”比没做 SLO 更危险

因为没有 SLO：

大家知道：

> 不知道。

False PASS：

系统告诉大家：

> 已经证明满足目标。

但其实没有证据。

所以：

```text
Unknown
```

和：

```text
Pass
```

必须严格区分。

这也是为什么 Evaluator 支持：

```text
PASS
FAIL
NOT_ENOUGH_EVIDENCE
```

------

# 三十八、Stage9 最终 Owner Matrix

这是整个阶段最值得背熟的表。

| Concern                 | Canonical Owner                   |
| ----------------------- | --------------------------------- |
| Authentication          | AuthService                       |
| Object Authorization    | ObjectAuthorizationService        |
| Run Execution           | DurableRunControlService          |
| Tool Catalog            | ToolRegistry                      |
| Tool Discovery          | ToolDiscovery                     |
| Run Tool Contract       | PostgreSQL ToolResolutionSnapshot |
| Tool Governance         | ToolGovernanceService             |
| Approval                | DurableApprovalService            |
| Continuation Scheduling | GenericContinuationService        |
| Tool Execution Claim    | Existing Durable Execution Claim  |
| Provider Execution      | ToolExecutionService              |
| Tool Side-effect Truth  | DurableToolInvocationService      |
| Client Delivery Feed    | PostgreSQL Client Event Feed      |
| Capacity Config         | Settings / existing Runtime Owner |

Final Gate：

```text
SECOND_AUTHORITY = NO
```



------

# 三十九、Stage9 最核心的设计思想

整个 Stage9 看下来，本质上是在做一件事：

> **把不同生命周期的 Ownership 分离。**

比如：

```text
连接生命周期
!= Run 生命周期

Run 生命周期
!= Continuation 生命周期

Continuation 生命周期
!= ToolInvocation 生命周期

ToolInvocation 生命周期
!= Provider Side Effect 生命周期
```

再分别为它们设计：

```text
Truth
Owner
Claim
Fence
Recovery
```

这比单纯“写一个 Agent Loop”复杂得多。

------

# 四十、Stage9 最值得记住的 Truth / Authority 分层

可以这样背：

```text
Who are you?
→ Authentication

Can you touch this object?
→ Object Authorization

Who owns this Run now?
→ Run Lease + Fence

Which Tools does this Run know?
→ Tool Snapshot

Can this Tool be invoked now?
→ Governance

Has a human approved it?
→ Approval

Who resumes this suspended task?
→ Continuation Claim

Who owns this side effect?
→ Tool Execution Claim

Did the side effect really happen?
→ DurableToolInvocation

What can the client replay?
→ Client Feed
```

这是非常适合架构面试的表达。

------

# 四十一、Stage9 最值得记住的 8 个 Bad Cases

## 1. Connection Disconnect Cancel Run

错误：

```text
network loss
→ task cancelled
```

修复：

```text
subscription lifecycle
!= run lifecycle
```

------

## 2. Client 直接 Replay Runtime Journal

错误：

可能泄露内部数据。

修复：

```text
Client-safe Projection Feed
```

------

## 3. Snapshot 只在内存

错误：

```text
process restart
→ rediscover
→ contract drift
```

修复：

```text
PostgreSQL Durable Snapshot
```

------

## 4. Planner 用 Snapshot，但 Execution 查 Global Registry

错误：

模型仍然可以执行 Snapshot 外 Tool。

修复：

```text
snapshot-only resolution
```

------

## 5. Continuation Claim 被当成 Run Owner

错误：

恢复 Worker 可以直接改 Run。

修复：

```text
mandatory Run Lease / Fence
```

------

## 6. Worker Crash 后直接 Retry Tool

错误：

UNKNOWN 可能重复非幂等副作用。

修复：

```text
read DurableToolInvocation first
```

------

## 7. Active Runs 无界

错误：

```text
100 accepted
44 no terminal
```

修复：

```text
4-slot admission
```

------

## 8. Missing SLO Metric 默认 0

错误：

```text
missing evidence
→ PASS
```

修复：

```text
NOT_ENOUGH_EVIDENCE
```

------

# 四十二、30 秒项目总结

如果面试官问：

> Stage9 主要做了什么？

可以回答：

> “Stage9 我主要把 AgentCore 往 Runtime Platform 方向补了一层。先做 tenant-first 的 Object Authorization，然后把 `/api/v1` 的连接生命周期和 Run 生命周期拆开，增加 PostgreSQL Client Feed 和 cursor-based resumable SSE。Tool 这边加了 deterministic Top-K Discovery 和 per-Run durable Tool Snapshot，保证恢复时不重新 Discovery。再往后把 Stage8 的业务 Continuation 抽成 Generic Durable Continuation，用 claim token、lease、reaper 和 Run fencing 支持跨 Worker 恢复，同时保证 UNKNOWN 和 COMMITTED 都不会 blind retry。最后做了真实 PostgreSQL-backed Runtime 压测和 Candidate SLO，把无界 Active Run 造成的 terminal loss 修成 4-slot admission backpressure。”

------

# 四十三、2 分钟项目总结

> “Stage9 的目标不是继续加 Agent 功能，而是补 Runtime 的生产边界。第一块是 Authorization，我把 JWT Authentication 和 Object Authorization 分开，增加 tenant、owner、tenant-local admin 和 scoped service 的对象授权模型。第二块是 Resumability，`/api/v1` 里 Client disconnect 不再 cancel Run，Runtime Event 会投影成 PostgreSQL Client Feed，Client 用 cursor 和 Last-Event-ID 跨实例恢复 SSE。
>
> Tool 这块我没有让恢复时重新看最新 Registry，而是先做 deterministic Top-K Discovery，再把 selected tool identity、schema digest、provider identity 等持久化成 Run-level ToolResolutionSnapshot。恢复时只 load/validate/hydrate，Schema 或 Provider Drift 就 fail closed。
>
> 对长任务和审批，我又增加了 Generic Durable Continuation。Continuation Claim 只负责谁来恢复，真正执行还必须重新拿 Run Lease/Fence、检查 Approval 和 ToolInvocation，然后再走原来的 Tool Execution Claim。Worker Crash 后 Reaper 只把 PROCESSING 重新变 READY，绝不会直接 retry Provider；STARTED、UNKNOWN、COMMITTED 都明确禁止 blind retry。
>
> 最后我做了真实 Runtime Load Test。测试里曾发现 Active Runs 无界，100 个 accepted Run 有 44 个 90 秒后没有 terminal，后来增加 4-slot admission，把隐藏 backlog 转成可见的 start latency。现在单机单 worker scripted backend 下，c25 correctness 仍通过，但 Run Start p95 大约 2.7 秒，超过 2 秒 Candidate SLO，所以这个 FAIL 我保留了，没有把它包装成 Production SLA。”

------

# 四十四、高频追问：为什么不用 Temporal

回答：

> “目前需求只是审批后 Resume、Worker takeover 和少量 durable wait point，所以我做了最小 Durable Continuation 层。它没有 Workflow DSL、Timer、Signal、Activity Retry、Compensation 这些 Temporal 能力。如果后面长流程和跨服务 Saga 复杂度继续增加，我会评估 Temporal，而不是不断把 Continuation 扩成自研 Workflow Engine。”

------

# 四十五、高频追问：为什么不用 Redis 做等待状态

回答：

> “因为 Continuation、Run、Approval 这些属于业务恢复事实，进程或 Redis 丢数据不能让任务消失，所以 Durable Truth 放 PostgreSQL。Redis 或 Kafka 可以以后用来 wake-up 和加速，但不能成为恢复 Authority。”

------

# 四十六、高频追问：为什么不用 Kafka 做 SSE

回答：

> “当前 PostgreSQL Client Feed 已经能实现跨实例 Replay，而且 Stage9 的目标是先把 correctness 闭环。Kafka 更适合作为 wake-up/fan-out 优化，但如果现在就引入，会增加 Consumer offset、duplicate delivery 和运营复杂度。当前限制是每个 live subscriber 250ms polling，会对 DB 形成压力，这已经明确记录为后续优化点。”

------

# 四十七、高频追问：Tool Snapshot 会不会导致旧 Tool 永远不能升级

回答：

> “不会。Snapshot 是 per-Run 的。新 Run 会使用最新 Registry 和新 Schema；旧 Run为了保持前后 Contract 一致，只认创建时的 Snapshot。如果当前 Tool Schema 已经漂移，旧 Run fail closed，不会自动换成新 Contract。”

------

# 四十八、高频追问：你为什么选择 Fail Closed

回答：

> “因为 Resume 最危险的不是失败，而是在无法证明一致性的情况下继续执行。尤其 Tool、Approval 和 Side Effect，一旦 Schema、Provider Identity 或 Binding 漂移，继续执行的风险比明确失败更高，所以选择 fail closed，然后走 explicit repair 或重新创建 Run。”

------

# 四十九、高频追问：Exactly-once 怎么做的

回答时不要直接说“整个系统 Exactly-once”。

应该说：

> “我没有声称网络或整个分布式系统 exactly-once。SSE 是 at-least-once + cursor dedup。Approval、Continuation Claim 和 Tool Execution Claim 各自通过数据库 CAS/lease/fencing 保证 single winner。对于外部非幂等 side effect，如果结果未知就进入 UNKNOWN，不 blind retry。所以我更多是把 exactly-once 语义限制在可证明的本地 Claim Boundary。”

这个回答很重要。

------

# 五十、高频追问：你做的 Recovery 到底恢复什么

可以回答：

> “恢复的是 durable execution context，不是 Python stack。Run、Approval、ToolInvocation、Tool Snapshot、Continuation 都有 durable identity。新 Worker 从 PostgreSQL重新加载这些状态，通过 fence、digest 和 binding 检查以后重新进入现有 Runtime path，而不是把旧协程序列化恢复。”

------

# 五十一、高频追问：为什么需要两个数据库状态，一个 Run，一个 Continuation

回答：

> “它们表达不同生命周期。Run 是业务执行生命周期，Continuation 是暂停以后谁来恢复的 scheduling lifecycle。Run 可以存在但当前没有可执行 Continuation；Continuation 完成也不代表整个 Run 一定完成。所以不能合并成一个状态机，否则 Run Ownership 和 Resume Scheduling 会耦合。”

------

# 五十二、高频追问：你压测为什么不用真实 DeepSeek

回答：

> “因为我要测 Runtime 自身。如果把 DeepSeek 放进主 benchmark，结果会混入 Provider latency、quota 和网络波动。所以用 scripted backend 测 PostgreSQL、Run、SSE、Continuation 自身，Remote Provider capacity 单独标记为 NOT_TESTED，没有把单机结果外推成模型生产能力。”

------

# 五十三、高频追问：为什么 c25 SLO FAIL 还能说 Stage9 完成

回答：

> “因为 Stage9 的目标是建立可信的 Runtime Contract 和 Evidence，不是规定必须达到某个吞吐数字。c25 correctness 仍然通过，但 p95 超过 2 秒，所以 Candidate SLO 就应该 FAIL。这个 Fail 本身就是容量边界证据；如果为了阶段通过去修改 threshold，反而破坏了 SLO 的意义。”

------

# 五十四、如果再次遇到真实面试中的几个问题

## 1. “用户审批十分钟，连接怎么办？”

现在可以回答：

> “不会维持原 HTTP 请求。Run 和 Approval 状态持久化后结束当前连接，Client 后续用 SSE cursor reconnect。Approval 完成后 Durable Continuation 变 READY，由任意 Worker claim，重新拿 Run Fence、加载 Snapshot 和 Approval 后继续。”

------

## 2. “重连到另一台 Server 呢？”

> “没关系。Client Feed 在 PostgreSQL，不依赖原 Worker 内存。Client 带 Last-Event-ID，新实例直接读取 cursor 之后的 durable events。”

------

## 3. “Worker 在 Tool 请求发出去后挂了呢？”

> “新的 Worker不会因为 Continuation Requeue 就重新调用 Tool，而是读取 DurableToolInvocation。如果是 STARTED/UNKNOWN 就停止并进入 reconciliation；如果 COMMITTED 也不会再调用 Provider，只处理已有结果或 explicit repair。”

------

## 4. “100 个 Tool 怎么办？”

> “先通过 deterministic metadata Discovery 做 bounded Top-K，模型只看到候选 Tool；选中的 Tool Contract再持久化为 Run Snapshot，恢复时不重新 Discovery。Discovery 只负责 candidate selection，真正执行仍重新过 Governance。”

------

## 5. “做过压测吗？”

现在已经可以直接回答真实数据：

> “做过 PostgreSQL-backed Runtime load。单机单 worker scripted backend 下 Run Start 测到 c25，每档 100 样本，correctness 全通过，但 c25 p95 是 2.7 秒，超过 2 秒 Candidate SLO。Load Test 还真实发现过无界 Active Run 导致 accepted Run 无 terminal 的问题，后来改成 4-slot admission。”

------

# 五十五、Stage9 的已知限制

Final Gate 最终接受的 P2 主要有四类。

### Streaming

```text
PostgreSQL 250ms polling
No Kafka fan-out
No Client ACK
No retention
No live SSE soak proof
```

### Continuation

```text
No long-running scheduler daemon
No automatic UNKNOWN reconciliation
COMMITTED without durable result may require repair
```

### Capacity

```text
single machine / single worker
no long soak
no cluster scaling
no autoscaling
no production traffic replay
no remote LLM capacity claim
Tool load NOT_TESTED
c25 Candidate latency SLO FAIL
```

### Test Estate

仍有 4 个旧 Legacy/catalog 测试断言没有清理，但不属于当前生产 Contract blocker。

------

# 五十六、现在能在面试里真实声明什么

可以说：

```text
Tenant-first object authorization
/api/v1 connection/run lifecycle decoupling
PostgreSQL-backed resumable SSE
Cross-instance replay
Deterministic bounded Tool Discovery
Durable immutable per-Run Tool Snapshot
Generic Durable Continuation
Lease / Heartbeat / Reaper
Run fencing + stale worker rejection
Approval binding recheck
UNKNOWN / STARTED / COMMITTED no blind retry
PostgreSQL-backed real Runtime load evidence
Candidate SLO evaluation
```

这些已经有源码和测试支撑。

------

# 五十七、现在不能说什么

不要说：

```text
Production SLA
Multi-region HA
Temporal equivalent
Automatic UNKNOWN reconciliation
Large-scale cluster capacity
Remote LLM production capacity
Tool production capacity
Exactly-once network delivery
Generic Saga / Compensation platform
```

Final Gate 明确没有这些证据。

------

# 五十八、Stage9 最应该记住的 12 句话

1. **Authentication 解决“你是谁”，Authorization 解决“你能碰哪个对象”。**
2. **Connection Lifetime 不应该等于 Run Lifecycle。**
3. **Runtime Journal 不应该直接作为 Client Replay Feed。**
4. **Discovery 解决候选规模，Snapshot 解决 Run Contract 稳定性。**
5. **Snapshot 不是 Registry，也不是 Authorization。**
6. **Continuation Claim 只解决谁来恢复，不代表谁能执行 Run。**
7. **Claim Token 防旧 Continuation Worker，Run Fence 防旧 Run Owner。**
8. **Reaper 恢复的是 Scheduling，不是 Side Effect。**
9. **UNKNOWN 最大的原则是 No Blind Retry。**
10. **Backpressure 宁可表现成 latency，也不能表现成 silent task loss。**
11. **Synthetic Benchmark 不能冒充 Runtime Capacity Evidence。**
12. **没有 Evidence 应该是 NOT_ENOUGH_EVIDENCE，而不是 PASS。**

------

# 五十九、Stage9 的一句话总结

> **Stage9 把 AgentCore 从“已经有很多 Runtime Feature”的系统，进一步收敛成了一个在对象授权、连接恢复、Tool Contract、Worker Crash Recovery 和容量证据上都有明确 Owner、Durable Truth 与 Failure Semantics 的 Agent Runtime Platform。**

而 Stage9 最有价值的地方，不是又增加了多少类，而是很多原来模糊的关系现在都已经拆清楚了：

```text
连接
Run
Tool Contract
Approval
Continuation
Tool Side Effect
Client Delivery
Capacity Evidence
```

各自都有自己的：

```text
Owner
Truth
Claim
Fence
Recovery Rule
```

这就是这一阶段最核心的工程学习。