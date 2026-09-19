# Stage8-WP10 — Durable Ticket Continuation

## 1. 名词 / 概念速览

**TicketDraft**
Failure Triage 判定为 PRODUCT 后生成的问题单草稿，还不是外部 Ticket。

**Tool Approval**
对 `stage8_create_ticket` 这个真实外部副作用的人工授权。

**TicketContinuation**
审批完成以后，负责跨 HTTP 请求继续完成提单动作的持久化业务对象。

**Request Snapshot**
审批前冻结下来的 Ticket 请求内容，避免批准以后 TicketDraft 被修改导致“批准 A，执行 B”。

**Request Digest**
对稳定 Ticket Snapshot 做 canonical JSON + SHA256 得到的摘要，用来确认执行内容没有变化。

**Invocation Binding Digest**
Tool Approval 和具体 ToolInvocation 之间的绑定摘要，防止 Approval 被拿去执行另一条调用。

**Business Claim**
多个 Continuation Worker 同时处理同一任务时，PostgreSQL 的 `READY -> PROCESSING` 条件更新决定谁拥有业务处理权。

**Tool Execution Claim**
真正执行外部副作用前，由原 Tool Runtime 再做一次 execution claim，决定谁拥有副作用执行权。

**UNKNOWN**
外部副作用可能已经发生，但系统无法确认结果时的状态；此时不能盲目重试。

------

# 2. 本 WP 解决什么业务问题

WP9 已经闭到：

```text
FAILED
→ FailureEvidencePackage
→ Failure Triage
```

如果 Triage 认为：

```text
classification = PRODUCT
```

之前已经可以：

```text
→ TicketDraft
→ Tool Approval
```

但流程停在：

```text
用户已经 APPROVE
→ ?
```

没有明确 Owner 去继续做：

```text
create_ticket
→ Ticket Platform
→ ticket_id
```

WP10 补的就是这个断点。

现在：

```text
PRODUCT
→ TicketDraft
→ immutable snapshot
→ ToolInvocation
→ Tool Approval

APPROVE
→ TicketContinuation READY
→ process_ready_once()
→ PROCESSING
→ resume approved ToolInvocation
→ stage8_create_ticket
→ Ticket Platform
→ ticket_id / ticket_url
→ TicketContinuation SUCCEEDED
```

`TicketContinuationService` 已经成为审批后 downstream action 的 durable Owner。

------

# 3. 工程构建方法问答

## 为什么 APPROVE 以后不能直接在 HTTP 请求里创建 Ticket？

因为：

```text
审批请求生命周期
≠
外部业务动作生命周期
```

如果：

```text
POST /approve
→ create_ticket
→ Ticket Platform timeout
```

审批接口就同时承担了：

```text
审批状态
外部网络调用
业务恢复
```

职责会混在一起。

现在：

```text
Approval HTTP
→ 只记录 APPROVED
→ Continuation READY
→ 返回
```

真正提单由独立的：

```text
process_ready_once()
```

处理。

------

## 为什么 APPROVED 不等于 Ticket Created？

因为 Approval 只代表：

> 人允许执行这个动作。

不代表 Ticket Platform 已经真的创建成功。

所以：

```text
APPROVED
→ ticket_id 仍然可能为空
```

只有：

```text
Ticket Platform 返回 ticket_id / ticket_url
→ durable writeback
→ Continuation SUCCEEDED
```

以后才能说：

> Ticket Created。

------

## 为什么必须冻结 Ticket Request Snapshot？

因为 TicketDraft 可能在 Approval 后发生变化。

例如：

```text
Draft A
→ Approval A

后来 Draft 变成 B
```

如果 Worker 运行时重新读取当前 Draft：

```text
Approval A
→ Execute B
```

就破坏了审批语义。

所以现在在 Continuation 创建时冻结：

```text
request_snapshot
request_digest
approval_id
tool_invocation_id
invocation_binding_digest
```

后续执行前重新校验。

------

## Approval A 怎么防止执行 Invocation B？

执行前同时检查：

```text
Approval ID
Tool Invocation ID
Invocation Binding Digest
Request Digest
```

全部匹配。

如果有任何一个不一致：

```text
FAIL CLOSED
NO EXTERNAL SIDE EFFECT
```

所以：

```text
APPROVAL_A_EXECUTES_B = NO
```

------

## 为什么不能只保存 Approval ID？

因为 Approval ID 只能说明：

> 有一条审批记录。

它不能单独证明：

> 它批准的是哪一个 ToolInvocation、哪一组参数。

所以还需要：

```text
tool_invocation_id
+
invocation_binding_digest
```

把授权和具体动作绑定起来。

------

## Durable ToolInvocation 里为什么还需要 Snapshot？

当前 Runtime 不持久化完整 raw arguments 或完整 Tool output，只保存 Invocation digest、状态和 provider operation id。

所以 WP10 不能直接从 DurableToolInvocation 里恢复 Ticket 请求内容。

最终路线是：

```text
同一个 durable tool_invocation_id
+
Continuation 中冻结的 request_snapshot
→ rebuild invocation
→ recompute digest
→ 校验 Approval binding
```

而不是假装 Runtime 已经保存完整 payload。

------

## 为什么重新 build invocation 不算“批准 A 执行 B”？

因为 rebuild 以后不是直接执行。

还必须：

```text
recompute request digest
recompute invocation binding
```

与原 durable Approval / Invocation 完全一致。

也就是说：

> rebuild 只是恢复数据，digest verification 才决定它是不是原来的动作。

------

## WP10 中 Sol 修复的 Blocking P1 是什么？

审批前创建的 durable invocation：

```text
execution_claim_id = NULL
```

审批后准备真正执行时：

```text
ToolExecutionService.execute()
```

会带新的 execution claim 再次调用 `prepare()`。

原来的 immutable identity 检查认为：

```text
原 invocation 没 claim
新 invocation 有 claim
→ identity changed
```

于是直接拒绝执行。

结果就是：

```text
Approval 成功
Continuation READY
但永远执行不了 create_ticket
```

Sol 最终修成：

> 对同一个 APPROVED、相同 binding、仍为 `PREPARED` 的 invocation，允许一次性绑定 execution claim。

之后依然由原 Tool Runtime 完成：

```text
STARTED
→ COMMITTED / UNKNOWN
```

------

## 为什么这个 execution claim 可以后绑定，不算修改 immutable invocation？

因为真正被冻结的是：

```text
Tool
Arguments
Target
Risk binding
Approved action identity
```

execution claim 是：

> 谁获得这一次执行权。

它属于执行阶段的控制字段，而不是用户批准的业务内容。

所以只有在：

```text
same approved invocation
same binding
state = PREPARED
```

时允许一次性附加。

------

## Business Claim 和 Tool Execution Claim 有什么区别？

第一层：

```text
TicketContinuation
READY → PROCESSING
```

解决：

> 多个业务 Worker 谁处理这个 Continuation。

第二层：

```text
DurableApprovalService.claim_execution()
```

解决：

> 谁真正拥有 Tool 副作用执行权。

两层不能混为一谈。

即使业务层因为异常重复触发：

```text
Tool Runtime
```

仍然还有自己的 claim 做最终副作用控制。

------

## 两个 Worker 同时处理怎么办？

两个 Worker 都看到：

```text
READY
```

然后竞争 PostgreSQL 条件更新：

```text
READY
→ PROCESSING
```

只有一个成功。

最终：

```text
CONCURRENT_WORKER_BEHAVIOR =
ONE_PROCESSING_WINNER / ONE_EXTERNAL_EXECUTION
```

------

## 重复调用 process_ready_once 会不会提多个 Ticket？

不会。

因为：

```text
READY
→ PROCESSING
```

只允许一个 winner。

成功后：

```text
SUCCEEDED
```

不再进入 ready scan。

UNKNOWN 也会被排除。

所以：

```text
DUPLICATE_PROCESSING = ONE_EXTERNAL_TICKET
```

------

## REJECT 之后呢？

直接：

```text
PENDING_APPROVAL
→ REJECTED
```

然后：

```text
create_ticket calls = 0
```

即使再次触发 process：

```text
REJECTED
```

也不会进入执行。

------

## 为什么 stage8_create_ticket 还是 NON_IDEMPOTENT？

因为当前 Mock / 真实业务 Contract 没有证明 Ticket Platform 支持稳定 Provider Idempotency。

所以不能为了方便重试，就声明：

```text
IDEMPOTENT_WITH_KEY
```

创建正式 Ticket 本身属于高风险、非幂等副作用。

------

## 外部调用 timeout 怎么办？

最危险场景：

```text
Ticket Platform 可能已经创建 Ticket
↓
response timeout
↓
AgentCore 不知道结果
```

这时不能：

```text
retry create_ticket
```

否则可能产生重复 Ticket。

所以：

```text
Continuation = UNKNOWN
BLIND_RETRY = NO
```

------

## UNKNOWN 为什么是终态？

当前没有 provider reconciliation 能力。

所以 UNKNOWN 会被：

```text
excluded from READY scan
```

不会自动再次执行。

它表示：

> 必须先确认外部事实，再决定怎么处理。

------

## 为什么不追求“绝对 Exactly-once”？

因为 AgentCore 只能控制自己。

内部可以保证：

```text
一个 approved invocation
→ 一个 execution claimant
```

但如果外部 Ticket Platform：

```text
已经执行
→ response 丢失
```

AgentCore 无法仅靠本地数据库判断外部是否成功。

所以准确表达应该是：

> AgentCore 内部提供 exactly-once-like execution control；外部非幂等系统的未知结果进入 UNKNOWN，不盲目 retry。

------

## Tool COMMITTED 后，业务 writeback 前崩溃怎么办？

当前这是明确 Accepted P1。

场景：

```text
Ticket Platform success
→ ToolInvocation COMMITTED
→ process crash
→ TicketContinuation 还没写 ticket_url
```

Runtime 当前只有：

```text
provider operation id
```

没有持久化完整 Tool result。

所以重启以后不能自动恢复：

```text
ticket_url
```

但也绝不能再 create Ticket。

------

## READY → PROCESSING 后 Worker 崩了怎么办？

当前没有 lease/reaper。

所以可能：

```text
PROCESSING forever
```

这是第二个 Accepted P1。

没有为了这一点在 WP10 里搭通用 HA Worker Framework。

------

## 为什么这轮没有用 Kafka？

因为当前真正需要的正确性已经由：

```text
PostgreSQL durable continuation
```

保证。

即使 HTTP 请求结束，甚至进程重启：

```text
READY continuation
```

还在数据库里。

以后再次：

```text
process_ready_once()
```

仍然可以继续。

Kafka 更适合解决：

> 谁自动、及时地唤醒 Worker。

而不是：

> 任务是否存在。

所以：

```text
KAFKA_USED = NO
OUTBOX_USED = NO
KAFKA_REQUIRED_FOR_CORRECTNESS = NO
```

------

## 如果未来加 Kafka，Kafka 应该做什么？

例如：

```text
Approval APPROVED
→ Outbox
→ Kafka: TicketContinuationReady
→ Worker
```

但 Worker 收到消息以后仍然必须重新读取：

```text
PostgreSQL Approval
TicketContinuation
ToolInvocation
```

Kafka 消息本身不是授权事实。

------

## ticket_id 是谁决定的？

Ticket Platform。

不能由：

```text
LLM
TicketDraft
caller
```

提供。

只有 Provider 成功返回：

```text
ticket_id
ticket_url
```

以后才能持久化到 Continuation。

------

# 4. 30 秒项目回答

> Product 类测试失败经过 Triage 后，会先生成 TicketDraft 和 Tool Approval。批准以后我没有在原 HTTP 请求里直接提单，而是创建一个 PostgreSQL 持久化的 TicketContinuation，把 Ticket 请求快照、Approval、ToolInvocation 和 binding digest 固定下来。后续 Worker 重新校验这些绑定，通过原 Tool Runtime 的 resume 路径执行 stage8_create_ticket。重复处理和并发 Worker 最终只有一个执行 winner。如果外部提单结果不确定，就进入 UNKNOWN，不会因为重试造成重复 Ticket。

------

# 5. 2 分钟项目回答

> WP10 解决的是 Product Failure 在人工审批以后怎么继续完成真实提单。
>
> 前面已经有 TicketDraft 和 Tool Approval，但批准以后没有持久化 Owner，所以 HTTP 请求结束以后这条流程就断了。
>
> 我新增了 TicketContinuation。创建时会冻结 Ticket request snapshot 和 request digest，同时保存 approval_id、tool_invocation_id 和 invocation binding digest。这样后面即使 TicketDraft 被修改，也不能拿旧 Approval 执行新内容。
>
> 审批本身只把 Continuation 推进到 READY，不直接调 Ticket Platform。后续独立的 process_ready_once 通过 PostgreSQL 的 READY→PROCESSING 条件更新竞争业务处理权，然后重新读取 Approval，验证它确实是 APPROVED，并校验 invocation identity 和 binding。
>
> 真正执行时没有绕开原来的 Tool Runtime，而是通过 GovernedToolInvoker.resume_approved 恢复原来的 stage8_create_ticket。Tool Runtime 里面还有 execution claim 和 durable side-effect state，所以 Business Claim 和 Tool Claim 是两层。
>
> Ticket 创建是 NON_IDEMPOTENT。如果外部请求超时，无法确认是否已经创建，就进入 UNKNOWN，绝不盲目 retry。成功以后，ticket_id 和 ticket_url 只能来自 Ticket Platform，并写回 TicketContinuation。
>
> 当前没有 Kafka，因为 PostgreSQL continuation 已经保证任务跨请求、跨重启仍存在。Kafka 以后更适合做自动唤醒，而不是保存业务 Truth。

------

# 6. 高频追问 + 简答

## 为什么要单独搞 TicketContinuation？

因为：

```text
Approval
```

只负责授权，

而：

```text
TicketContinuation
```

负责授权之后谁继续执行和保存结果。

------

## 为什么 ApprovalController 不直接执行？

因为审批请求不应该绑定外部平台调用生命周期。

------

## 为什么不用一个 callback？

内存 callback 在进程重启以后会丢。

Continuation 在 PostgreSQL 中，是 durable 的。

------

## 为什么还需要 Tool Runtime？

因为 TicketContinuation 只是业务流程 Owner。

真正副作用 Authority 仍然应该统一由 Tool Runtime 控制。

------

## 为什么有两层 claim？

Business claim 控制：

```text
谁处理 Continuation
```

Tool claim 控制：

```text
谁真正执行副作用
```

------

## 为什么不能只靠 Continuation claim？

因为 Tool Runtime 还可能被其他入口调用。

副作用安全必须由统一 Runtime 保证，而不能依赖 Stage8 业务代码。

------

## 为什么 APPROVE 后不能重新 build 一个新 Tool Call？

因为可能变成：

```text
Approval A
→ Invocation B
```

------

## 那你现在不是也 rebuild 了吗？

数据上需要从 snapshot 恢复，但 rebuild 后必须重新计算 digest，并与原 Approval / durable invocation binding 完全一致。

不是“重新决定一个动作”。

------

## 为什么 UNKNOWN 不 retry？

因为 create_ticket 是 NON_IDEMPOTENT。

可能已经创建成功。

------

## 如果 Ticket Platform 支持 request_id 幂等呢？

那以后可以把 Provider Contract 升级为：

```text
IDEMPOTENT_WITH_KEY
```

然后 UNKNOWN recovery 可以更积极。

但当前没有这个事实，所以不能假设。

------

## 为什么不用 Saga？

当前只有一个很小的 downstream action，不需要搭通用 Saga Framework。

------

## 为什么不用 Temporal？

如果以后审批、等待、重试、补偿和长流程越来越多，Temporal 是合理评估项。

当前 Stage8 状态不多，用 PostgreSQL durable state + CAS 更快，也更容易说明 Owner。

------

## Kafka 在这里没用是不是之前设计错了？

不是。

Kafka 是可选调度手段，不是业务正确性的基础。

先有 durable business operation，再决定谁来触发它。

------

## 现在服务重启还能继续吗？

如果 Continuation 仍是：

```text
READY
```

可以重新调用 `process_ready_once()`。

如果已经：

```text
PROCESSING
```

然后进程崩溃，当前没有 lease/reaper，这还是 Accepted P1。

------

## Ticket 创建成功但 writeback 崩了怎么办？

当前不能自动恢复完整 ticket result，因为 Runtime 没持久化完整 Tool output。

但不会再次提单。

------

# 7. Bad Case

## Real Bad Case 1 — Approved 但永远执行不了

初版真正发现：

```text
ToolInvocation PREPARED
execution_claim_id = NULL

Approval APPROVED

resume
→ new execution claim
→ prepare()
→ immutable identity mismatch
→ execution rejected
```

最终修复：

```text
same APPROVED invocation
+
same binding
+
PREPARED
→ allow one-time execution claim binding
```

这是本 WP 最大的真实 Blocking P1。

------

## Real Bad Case 2 — Approval A 执行 Payload B

错误：

```text
Draft A
→ approve

Draft changed to B

Worker reads current Draft
→ create B
```

现在冻结 Snapshot + Digest + Invocation Binding，执行前全部校验。

------

## Real Bad Case 3 — 重复 Approve 把 PROCESSING 改回 READY

如果两个 Approve callback 连续到达：

错误实现可能：

```text
PROCESSING
→ READY
```

又重新触发一次执行。

Sol 已修复：

> duplicate approve callback 不能 reopen PROCESSING。

------

## Real Bad Case 4 — 确定性失败一直回 READY

错误：

```text
Tool deterministic failure
→ READY
→ retry
→ READY
→ retry
```

可能形成无限循环。

现在确定性失败进入：

```text
FAILED
```

不自动 retry。

------

## Real Bad Case 5 — Provider 返回空 Ticket ID 还标成功

错误：

```text
create_ticket result
ticket_id = ""
→ Continuation SUCCEEDED
```

Sol 已修成：

```text
ticket_id / ticket_url
必须非空
```

否则不能写 SUCCEEDED。

------

## Accepted Bad Case 1 — PROCESSING 崩溃

```text
READY
→ PROCESSING
→ crash
```

当前没有 lease/reaper。

可能卡住，需要后续生产增强。

------

## Accepted Bad Case 2 — COMMITTED 后 writeback 崩溃

```text
external Ticket created
→ Tool COMMITTED
→ process crash
→ Continuation 没 ticket_url
```

当前不能自动修复，但绝不重新 create。

------

# 8. Truth / Owner / Completion Boundary

## PRODUCT Classification

Owner：

```text
Failure Triage Result
```

输入基于：

```text
ExecutionResult
FailureEvidencePackage
```

caller 不能自己声明 PRODUCT。

------

## TicketDraft

Owner：

```text
PRODUCT Triage Output
```

是准备内容，不是 Ticket。

------

## Ticket Request Snapshot

Owner：

```text
TicketContinuation
```

创建时冻结。

------

## Approval State

Owner：

```text
DurableApprovalService + PostgreSQL
```

------

## Approved Tool Action

Owner：

```text
tool_invocation_id
+
invocation_binding_digest
```

------

## Ticket Continuation State

Owner：

```text
TicketContinuationService + PostgreSQL
```

------

## Business Claim

Owner：

```text
Stage8 PostgreSQL conditional update
```

------

## Tool Execution Claim

Owner：

```text
DurableApprovalService / Tool Runtime
```

------

## External Ticket Creation

Owner：

```text
Ticket Platform
```

------

## ticket_id / ticket_url

Owner：

```text
Ticket Platform response
```

不是 Agent。

------

## Tool Invocation Side-effect State

Owner：

```text
ToolExecutionService
```

包括：

```text
PREPARED
STARTED
COMMITTED
UNKNOWN
```

------

## WP10 已完成

真实完成：

```text
PRODUCT Triage
→ TicketDraft
→ durable Approval
→ immutable request snapshot
→ TicketContinuation
→ APPROVE
→ durable continuation
→ business claim
→ original Tool Runtime resume
→ Ticket Platform
→ durable ticket identity writeback
```

并且：

```text
Reject zero execution
Approval A cannot execute B
duplicate processing safe
concurrent worker safe
no second Approval
UNKNOWN no blind retry
```

------

## WP10 未完成

当前没有：

```text
Kafka / Outbox auto wakeup

real enterprise Ticket Platform auth/transport

provider idempotency

UNKNOWN reconciliation

PROCESSING lease/reaper

post-COMMITTED business writeback repair

Stage8 object-level RBAC
```

------

# 9. 当前 Stage8 完整业务主链

做到 WP10 后，当前主链已经闭成：

```text
Feature
→ Feature Understanding
→ Risk Analysis
→ TestPlan
→ Human Review

→ Case Generation Platform
→ GeneratedCaseArtifact

→ Environment Platform
→ Environment Selection
→ execution-list.xls

→ Test Execution Platform
→ ExternalExecutionJob

→ Provider Observation
→ deterministic result parser

SUCCESS
→ Mission COMPLETED

FAILED
→ FailureEvidencePackage
→ Failure Triage

PRODUCT
→ TicketDraft
→ Tool Approval
→ Durable TicketContinuation
→ Ticket Platform
→ ticket_id / ticket_url
```

从这里开始，剩下的主要是：

```text
生产可靠性补强
```

而不是主业务流程缺了一截。

------

# 10. 本 WP 最应该记住的五句话

第一句：

> **Approval 只负责授权，Continuation 才负责审批以后跨请求继续完成业务动作。**

第二句：

> **批准的必须是具体 ToolInvocation，而不是“某个大概类似的 Ticket 请求”。**

第三句：

> **业务 claim 和 Tool execution claim 是两层，前者控制 Worker，后者控制真正副作用。**

第四句：

> **对于 NON_IDEMPOTENT 外部动作，结果不确定时宁可 UNKNOWN，也不能盲目 retry。**

第五句：

> **Kafka 可以负责唤醒 Worker，但 PostgreSQL 才保存 Approval、Continuation 和 Ticket 的真实状态。**