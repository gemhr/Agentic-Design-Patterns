# Stage5-Phase7 — Tool Approval HITL

## 1. Phase 定义

Stage5-Phase7 的目标是为 LocalAgent 建立一套：

> **Minimum Credible Tool Approval HITL（最小可信工具审批人在回路） + Human-facing UI Closure（面向人的 UI 闭环）**

核心问题是：

当 Agent 即将执行具有真实副作用的高风险 Tool 时，不能只依赖模型自行判断，也不能简单把高风险 Tool 永久拒绝，而应该：

```text
识别高风险 Tool
→ 在副作用发生前暂停当前 Step
→ 向 Human 暴露安全审批上下文
→ Human Approve / Reject
→ Runtime 安全处理决定
→ Approve 后至多执行一次
→ Reject / Cancel / Timeout 后不执行
→ 将整个过程形成可验证 Evidence
```

最终 Stage5-Phase7 Gate：

```text
STAGE5_PHASE7_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

WP1_TOOL_APPROVAL_RUNTIME_CORE = PASS
WP2_APPROVAL_TRANSPORT = PASS
WP3_HITL_EVALUATION = PASS

RUNTIME_OWNER_BOUNDARY = PASS
PUBLIC_API_BOUNDARY = PASS
SIDE_EFFECT_SAFETY = PASS
EVALUATION_AUTHORITY = PASS
INTERVIEW_CREDIBILITY = PASS

PHASE7_BLOCKING_P0 = 0
PHASE7_BLOCKING_P1 = 0
PHASE7_ACCEPTED_P1 = 4
PHASE7_ARCHITECTURE_REOPEN_REQUIRED = NO
```

在上述 Gate 后补充完成：

```text
WP4 — Minimal Approval UI Closure

WP4_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS
PHASE7_UI_CLOSURE = PASS
BACKEND_CONTRACT_UNCHANGED = YES
BLOCKING_P0 = 0
BLOCKING_P1 = 0
ARCHITECTURE_REOPEN_REQUIRED = NO
```

因此最终准确范围为：

```text
MINIMUM_CREDIBLE_TOOL_APPROVAL_HITL
+
HUMAN_FACING_UI_CLOSURE
```

它不等于 Production Approval Platform，也不代表已经实现 Authentication、RBAC、Restart Recovery 或 Durable Workflow。

------

# 2. 为什么 Agent 需要 HITL

传统 Chatbot 的主要风险是：

```text
生成错误文本
```

而 Agent 会：

```text
理解任务
→ 制定 Plan
→ 选择 Tool
→ 调用外部系统
→ 修改真实世界状态
```

真实副作用可能包括：

```text
修改文件
修改数据库
调用写 API
删除资源
执行脚本
修改配置
触发业务操作
```

因此 Agent Safety 的关键问题从：

> “模型回答错了怎么办？”

变成：

> “模型决策错误时，如何避免错误直接转化为不可逆副作用？”

两个极端方案都不理想：

```text
所有 Tool 自动执行
→ 自动化强，但风险高

所有 Tool 人工审批
→ 安全，但 Agent 自动化价值下降
```

Phase7 采用：

> **Risk-based HITL（基于风险的人在回路）**

只有被 Tool Governance 判定需要人工批准的操作进入 Approval Gate。

------

# 3. Phase7 的四个 WP

## WP1 — Tool Approval Runtime Core

解决：

> Runtime 内部如何真正进入等待审批，并安全处理 Approve / Reject / Cancel / Timeout。

核心能力：

```text
ToolApprovalController
WAITING_FOR_APPROVAL
ApprovalRequest
ApprovalDecision
ApprovalStatus
decision CAS
execution claim
immutable invocation binding
Journal-first approval evidence
```

------

## WP2 — Approval API / Streaming / Lifecycle

解决：

> Client 如何知道需要审批，又如何把 Human Decision 传回 Runtime。

采用：

```text
Observation Channel
→ /api/chat stream

Command Channel
→ HTTP POST approve / reject
```

同时保持 HTTP / Stream 都只是 Transport，不拥有 Approval Truth。

------

## WP3 — HITL Evaluation / E2E

解决：

> 如何证明 HITL 的安全性，而不仅仅是“代码能跑”。

AgentEvalOps 新增：

```text
typed HITL evidence
correlation
evidence completeness
Assertions A-F
PASS / FAIL / BLOCKED
synthetic bad cases
real LocalAgent → AgentEvalOps E2E
```

------

## WP4 — Minimal Approval UI Closure

解决：

> Human 如何真正看见 Approval，并在 Desktop Client 中完成操作。

新增：

```text
TOOL_APPROVAL_REQUESTED
→ Approval Card
→ Approve / Reject
→ existing HTTP API
→ TOOL_APPROVAL_DECIDED
→ UI terminal state
```

WP4 没有重新打开 Runtime、HTTP Contract 或 Evaluation Architecture。

------

# 4. 最终完整用户链路

Phase7 最终真实链路：

```text
User Request
    ↓
Agent Planning
    ↓
Tool Invocation
    ↓
ToolGovernanceService
    ↓
APPROVAL_REQUIRED
    ↓
ToolApprovalController
    ↓
Step = WAITING_FOR_APPROVAL
Run  = RUNNING
    ↓
Journal-first
TOOL_APPROVAL_REQUESTED
    ↓
[[ORCH]] Streaming
    ↓
Desktop Approval Card
    ↓
Human
 ┌───────────────┐
 │ Approve/Reject│
 └───────┬───────┘
         ↓
HTTP Command
         ↓
RunRegistry
         ↓
ToolApprovalController
         ↓
Decision CAS

APPROVE
    ↓
APPROVED
    ↓
Execution Claim
    ↓
EXECUTION_CLAIMED
    ↓
Original Immutable Invocation
    ↓
ToolExecutionService
    ↓
Tool side effect <= 1

REJECT
    ↓
zero Tool execution

CANCEL / TIMEOUT before claim
    ↓
approval invalidated
    ↓
zero Tool execution

         ↓
Runtime Journal
         ↓
Safe Evidence Projection
         ↓
AgentEvalOps
         ↓
PASS / FAIL / BLOCKED
```

------

# 5. 最终 Owner Boundary

Phase7 非常重要的一点是没有形成多套状态 Owner。

## ToolGovernanceService

负责：

```text
ALLOW
DENY
APPROVAL_REQUIRED
```

它判断风险，但不负责 Human Waiting。

------

## ToolApprovalController

负责：

```text
pending approval
decision
decision CAS
execution claim
wait / wake
```

它是 Approval Business Truth Owner。

------

## AgentState / AgentStateMachine

负责：

```text
Step lifecycle
```

例如：

```text
RUNNING
→ WAITING_FOR_APPROVAL
→ RUNNING / FAILED / CANCELLED
```

------

## RunCoordinator

负责：

```text
Run terminal lifecycle
```

------

## RunRegistry

负责：

```text
active Run command forwarding
```

但不保存 Approval Business Truth。

------

## ToolExecutionService

负责：

```text
真正执行 Tool
```

------

## HTTP / Streaming / Desktop UI

负责：

```text
Transport
Projection
Human Interaction
```

都不是 Runtime Truth Owner。

------

## AgentEvalOps

负责：

```text
Evidence Evaluation
```

它只能读取 Runtime Facts：

```text
事实发生了什么？
```

不能控制：

```text
接下来 Runtime 应该发生什么？
```

最终 Gate 明确确认 Evaluation Authority 与 Runtime Authority 没有混淆。

------

# 6. 为什么新增 WAITING_FOR_APPROVAL

原有：

```text
PENDING
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

不能准确表示 HITL。

审批发生时：

```text
Step 已被 Scheduler claim
Worker 已启动
Tool Invocation 已形成
Governance 已执行
```

因此不能重新退回：

```text
PENDING
```

否则会把：

> “执行到了人工审批边界”

错误表达成：

> “任务尚未开始”。

最终新增：

```text
WAITING_FOR_APPROVAL
```

表示：

```text
Step 已启动
但当前等待 Human Decision
```

------

# 7. 为什么 Run 仍然保持 RUNNING

一个 Step 等待审批并不代表整个 Run 停止。

例如：

```text
Run
├── Step A → WAITING_FOR_APPROVAL
├── Step B → RUNNING
└── Step C → SUCCEEDED
```

因此没有新增：

```text
RunStatus.PAUSED
```

而是保持：

```text
Run = RUNNING
Step = WAITING_FOR_APPROVAL
```

这使 HITL 与现有 DAG / Scheduler Contract 更兼容。

------

# 8. Approval 不等于 Execution

Phase7 最核心的设计原则之一：

> **Human Approve 只代表允许执行，不代表 Tool 已获得执行资格。**

错误模型：

```text
HTTP Approve
→ Execute Tool
```

存在重复请求和并发风险。

最终模型：

```text
PENDING
    ↓
APPROVE
    ↓
APPROVED
    ↓
original worker wakes
    ↓
atomic claim_execution()
    ↓
EXECUTION_CLAIMED
    ↓
ToolExecutionService
```

因此：

```text
APPROVED
```

表示：

> Human Business Authorization

而：

```text
EXECUTION_CLAIMED
```

表示：

> 某个 worker 获得唯一执行资格。

------

# 9. At-most-once 与 Exactly-once

Phase7 当前保证的是：

> **single-process at-most-once**

即：

```text
Tool execution count <= 1
```

这与：

> distributed exactly-once

完全不同。

当前没有：

```text
distributed consensus
persistent execution lease
multi-node CAS
restart reconciliation
distributed lock
```

因此面试必须准确表述为：

```text
single-process at-most-once
```

不能夸大为 distributed exactly-once。

------

# 10. CAS 如何处理人工决策竞争

## Duplicate Approve

```text
PENDING
→ APPROVED
```

第一次成功。

第二次看到已经：

```text
APPROVED
```

返回：

```text
200
idempotent=true
```

但不会再次：

```text
publish
wake
claim
execute
```

------

## Approve vs Reject

规则：

> First successful decision wins。

例如：

```text
APPROVE
→ APPROVED

late REJECT
→ 409 APPROVAL_DECISION_CONFLICT
```

不会后写覆盖前写。

------

# 11. Approve 与 Cancel Race

最重要窗口：

```text
APPROVED
但
未 EXECUTION_CLAIMED
```

如果此时 Cancel：

```text
Cancel
→ invalidate approval
→ execution claim fails
→ zero Tool execution
```

因此：

> Human Approve 并不意味着执行从此不可取消。

真正不可越过的边界是 Execution Claim。

------

# 12. Immutable Invocation Binding

Phase7 一个非常重要的安全问题是：

> Human 批准的 Invocation 必须与最后执行的 Invocation 完全一致。

WP1 Final Gate 真实发现原 claim 边界主要校验：

```text
invocation_id
tool_name
```

理论上可能：

```text
Approval:
id=X
tool=update_config
args=A

Execution:
id=X
tool=update_config
args=B
```

这属于：

> **TOCTOU（Time-of-Check to Time-of-Use，检查时与使用时竞态）**

最终 claim 加强绑定：

```text
invocation id
tool name
arguments digest
idempotency-key digest
resource-key digest
```

因此：

```text
Approval(A)
→ Execution(A)
```

不能变成：

```text
Approval(A)
→ Execution(B)
```

这是 Phase7 最值得在面试中讲的安全工程案例之一。

------

# 13. Journal-first

审批属于高风险副作用的授权证据。

因此顺序不能是：

```text
Runtime APPROVED
→ later Journal write
```

如果 Journal 失败：

```text
Runtime 已认为批准
Evidence 却没有批准记录
```

可能出现无法审计的 Tool execution。

所以采用：

```text
TOOL_APPROVAL_REQUESTED
→ Journal success
→ Pending effective
```

Approve：

```text
TOOL_APPROVAL_DECIDED(APPROVED)
→ Journal success
→ APPROVED effective
→ execution claim
→ TOOL_STARTED
```

最终核心顺序：

```text
TOOL_APPROVAL_REQUESTED
<
TOOL_APPROVAL_DECIDED(APPROVED)
<
TOOL_STARTED
```

------

# 14. Fail Closed

HITL 的核心安全原则：

> 无法证明安全时，不执行。

例如：

```text
binding mismatch
Journal publication failure
controller unavailable
invalid lifecycle
timeout
cancel
```

不能：

```text
Approval subsystem error
→ continue execution anyway
```

必须：

```text
fail closed
→ zero Tool execution
```

------

# 15. WP2：Observation 与 Command 分离

Phase7 没有构建双向 Streaming Protocol。

而是：

```text
Observation Channel
Runtime → Client
```

通过 `/api/chat` stream。

以及：

```text
Command Channel
Client → Runtime
```

通过 HTTP POST。

可以把它理解为轻量：

> Command / Observation Separation

但不要包装成系统完整实现了 CQRS。

------

# 16. HTTP Routes

最终：

```text
POST /api/runtime/runs/{run_id}/tool-approvals/{approval_id}/approve

POST /api/runtime/runs/{run_id}/tool-approvals/{approval_id}/reject
```

Request body：

```json
{
  "invocation_binding_digest": "..."
}
```

`actor_id` 是 optional audit label，不是 authentication principal。

------

# 17. 为什么 Public API 不暴露 raw invocation_id

公共 correlation 使用：

```text
run_id
+
approval_id
+
invocation_binding_digest
```

而不是 raw internal ID。

`invocation_binding_digest` 表达的是：

> 与被冻结 Invocation 和风险事实相关的完整性绑定。

这比只传 Tool name 或 raw internal identifier 更安全。

------

# 18. Digest 不等于 Authorization

必须严格区分：

```text
Correlation / Integrity
```

与：

```text
Authentication / Authorization
```

`approval_id + binding_digest` 只能回答：

> “这个命令对应哪一次 Approval？”

不能回答：

> “调用者是谁？”

也不能回答：

> “调用者有没有批准权限？”

因此当前真实状态：

```text
HUMAN_DECISION_TRANSPORT = IMPLEMENTED

AUTHENTICATION = NOT_IMPLEMENTED
AUTHORIZATION = NOT_IMPLEMENTED
RBAC = NOT_IMPLEMENTED
```

不能把 binding digest 包装成安全凭据。

------

# 19. HTTP Status Taxonomy

## First Approve / Reject

```text
200
```

------

## Duplicate same decision

```text
200
idempotent=true
```

------

## Opposite decision

```text
409
APPROVAL_DECISION_CONFLICT
```

------

## Active Run 内 unknown approval

```text
404
APPROVAL_UNKNOWN
```

------

## Run 已失效

```text
410
APPROVAL_RUN_INACTIVE
```

------

## Binding mismatch

```text
409
APPROVAL_BINDING_MISMATCH
```

------

## Cancel / Timeout 后 approval 失效

```text
410
APPROVAL_INVALIDATED
```

HTTP 只是把 Runtime Domain Result 投影成稳定 Transport Contract。

------

# 20. Invalidated vs Idempotent

WP2 实施中真实出现：

```text
APPROVE
→ CANCEL
→ late APPROVE
```

曾错误返回：

```text
200 idempotent
```

原因是代码先判断：

```text
same decision
```

再判断：

```text
invalidated
```

但：

```text
historically approved
```

不等于：

```text
currently effective approval
```

最终改为：

```text
INVALIDATED first
→ 410
```

再考虑 same-decision idempotency。

核心经验：

> **Lifecycle Validity 优先于 Historical Idempotency。**

------

# 21. Explicit Allowlist Projection

Runtime Event 不能：

```text
model_dump()
→ 全量暴露给客户端
```

否则内部未来增加：

```text
prompt
path
secret
raw args
```

可能自动泄露到 Public API。

Phase7 Streaming 只允许明确字段。

`TOOL_APPROVAL_REQUESTED`：

```text
approval_id
tool_name
invocation_binding_digest
risk_level
risk_facts
```

`TOOL_APPROVAL_DECIDED`：

```text
approval_id
invocation_binding_digest
decision_status
```

------

# 22. WP4：Approval Card

Desktop Client 收到：

```text
TOOL_APPROVAL_REQUESTED
```

后，在 Chat Timeline 中创建：

```text
┌───────────────────────────┐
│ 需要人工审批               │
│                           │
│ Tool: update_config       │
│ Risk: HIGH                │
│                           │
│ 风险原因                  │
│ · destructive_write       │
│                           │
│ [拒绝]          [批准]    │
└───────────────────────────┘
```

卡片只展示：

```text
tool_name
risk_level
risk_facts
```

不会展示：

```text
binding digest
raw invocation ID
raw tool arguments
path
prompt
secret
resource content
internal error
```

------

# 23. Presentation State 不等于 Runtime Truth

UI 最小状态：

```text
PENDING
SUBMITTING
APPROVED
REJECTED
EXPIRED
ERROR
```

它们只是：

> Presentation State

不是 Runtime：

```text
ApprovalStatus
StepStatus
RunStatus
```

因此：

```text
User clicked Approve
```

不能自动等价：

```text
Runtime APPROVED
```

点击后只能：

```text
PENDING
→ SUBMITTING
```

等待 HTTP / Runtime Event。

------

# 24. HTTP Result 与 Stream Event

两条信号来源承担不同职责。

## HTTP

告诉 UI：

> “刚刚提交的 command 怎么处理了？”

------

## Stream

告诉 UI：

> “Runtime 当前观察到的 lifecycle 是什么？”

可以概括为：

```text
HTTP
= Command acknowledgement

Stream
= Runtime lifecycle observation
```

------

# 25. HTTP / Stream Race

两条异步通道顺序不固定。

## HTTP first

```text
click Approve
→ HTTP 200
→ UI APPROVED
→ stream APPROVED
→ idempotent confirm
```

------

## Stream first

```text
click
→ SUBMITTING
→ stream APPROVED
→ UI APPROVED
→ late HTTP callback
```

Late callback 不能覆盖 terminal state。

------

# 26. Terminal Runtime Event Wins

Final Gate 特别补测：

```text
stream APPROVED
→ late HTTP network error
```

最终仍：

```text
APPROVED
```

而不是：

```text
ERROR
```

以及：

```text
stream INVALIDATED_TIMEOUT
→ late HTTP success
```

最终仍：

```text
EXPIRED
```

不能：

```text
APPROVED
```

因此 UI 采用：

```text
Runtime terminal observation
>
late HTTP result
>
intermediate presentation state
```

的 authority precedence。

------

# 27. Qt UI Thread Safety

网络请求不得运行在 Qt GUI thread。

最终：

```text
UI thread
→ click
→ disable buttons
→ SUBMITTING

background thread
→ HTTP POST

Qt signal
→ approval_result_signal

UI thread
→ update model/widget
```

Background thread 不调用：

```text
QWidget
layout
setText
setEnabled
```

所有 UI mutation 都回 Qt UI Thread。

------

# 28. Double Click

虽然 Backend 已有 Idempotency，

Frontend 仍然：

```text
first click
→ SUBMITTING
→ disable Approve
→ disable Reject
```

第二次点击：

```text
zero extra HTTP request
```

这是 Defense in Depth。

后端负责最终安全，

前端负责减少：

```text
重复请求
race
日志噪声
糟糕 UX
```

------

# 29. UI Correlation

每张卡通过：

```text
(run_id, approval_id)
```

唯一关联。

Card 内部还保存：

```text
invocation_binding_digest
```

Submit 时必须从这张卡自己的 Model 取：

```text
run_id
approval_id
binding digest
```

不能依赖：

```text
last approval
current approval
global current card
```

因此 Approval A 不会错误提交 Approval B 的 correlation。

------

# 30. Duplicate Requested

重复收到：

```text
same run_id + approval_id
```

不会创建第二张卡。

否则用户可能看到：

```text
同一次 Approval
→ 两组 Approve / Reject button
```

即便后端 CAS 安全，UI 也会非常混乱。

所以 UI projection 同样具有 Idempotency。

------

# 31. Run-scoped Cleanup

当：

```text
Run A
```

结束时，只 expire：

```text
Run A approval cards
```

不能影响：

```text
Run B
```

Final Gate 专门增加了：

```text
Run A terminal
→ Run A expired

Run B pending
→ unchanged
```

的回归测试。

------

# 32. Widget / Callback Lifecycle

异步 UI 常见场景：

```text
HTTP starts
→ chat reset
→ Card removed
→ HTTP callback arrives
```

Worker 不持有直接 QWidget pointer。

而是：

```text
(run_id, approval_id)
→ lookup model
```

找不到：

```text
no-op
```

避免：

```text
callback
→ deleted QWidget
→ crash
```

------

# 33. Production Contract vs Test Fake

WP4 一个非常好的真实工程问题：

生产代码新增：

```text
expire_pending_approvals()
```

旧 test fake 没实现。

初版为了兼容 fake：

```python
method = getattr(...)
if callable(method):
    method()
```

看起来“更安全”，实际上可能掩盖：

```text
production ChatPanel
缺少 required capability
```

最终 Codex 改成：

```text
production code
→ explicit required call

test fake
→ implement required interface
```

核心经验：

> **Required Composition Contract 缺失应该 Fail Fast，而不是被 optional guard 静默吞掉。**

------

# 34. WP3：为什么需要 Evaluation

即使 Runtime 和 UI 都能工作，也还需要回答：

```text
Tool 是否真的在 Approval 后才执行？

Reject 后有没有执行？

Duplicate approve 有没有执行两次？

Cancel / Timeout 后有没有 execution？

证据不足时会不会误判安全？
```

所以 AgentEvalOps 负责：

```text
Runtime Evidence
→ Validation
→ Correlation
→ Assertions
→ PASS / FAIL / BLOCKED
```

------

# 35. Typed Evidence

正式 evaluator 不允许：

```text
grep "APPROVED"
grep "TOOL_STARTED"
```

而是消费：

```text
HitlToolApprovalEvidenceV1
HitlRuntimeEventV1
```

并验证：

```text
run_id
sequence
event type
approval correlation
SHA-256 digest
trace completeness
provenance
```

------

# 36. HITL Assertions

## A — Approval Requested

需要审批的 scenario 必须出现：

```text
TOOL_APPROVAL_REQUESTED
```

------

## B — Approval Before Execution

必须：

```text
REQUESTED
<
DECIDED(APPROVED)
<
TOOL_STARTED
```

------

## C — Reject Prevents Execution

```text
REJECTED
→ zero TOOL_STARTED
```

------

## D — At-most-once

```text
one approved binding
→ TOOL_STARTED count <= 1
```

------

## E — Cancel Safety

```text
INVALIDATED_CANCELLED
→ no later TOOL_STARTED
```

------

## F — Timeout Safety

```text
INVALIDATED_TIMEOUT
→ no later TOOL_STARTED
```

------

# 37. Evidence Completeness

整个 WP3 最重要的知识点：

> **Absence of Evidence 不等于 Evidence of Absence。**

例如：

```text
REJECTED
```

以后没有看到：

```text
TOOL_STARTED
```

不一定说明 Tool 没执行。

也可能：

```text
日志没有完整采集
```

所以必须判断：

```text
trace_complete
```

------

# 38. PASS / FAIL / BLOCKED

## PASS

```text
证据完整
+
Invariant 满足
```

------

## FAIL

```text
证据足够
+
明确发现 Invariant 被违反
```

------

## BLOCKED

```text
证据不足
+
无法可靠判断
```

例如：

```text
REJECTED
trace_complete=False
no TOOL_STARTED observed
```

只能：

```text
BLOCKED
```

不能 PASS。

------

# 39. `trace_complete=True` 真实 Bad Case

WP3 初版真实 E2E 直接写：

```text
trace_complete=True
```

这会导致：

```text
TOOL_STARTED 没采到
+
trace_complete=True
→ zero execution PASS
```

可能产生 False PASS。

Final Gate 修成：

只有满足：

```text
Journal 从 sequence 0 开始完整读取
+
最后一条为 RUN_COMPLETED
+
读取真实 terminal status
```

才能：

```text
trace_complete=True
```

否则测试失败，无法产生 PASS。

核心经验：

> **Evidence Completeness 本身也必须有 Evidence。**

------

# 40. Correlation

Evaluator 不能仅判断：

```text
有没有 APPROVED
有没有 TOOL_STARTED
```

必须证明它们属于同一个 Lifecycle。

Approval 使用：

```text
run_id
+
approval_id
+
invocation_binding_digest
```

执行事件当前进一步依赖：

```text
invocation_identity_digest
```

进行 run-scoped correlation。

------

# 41. Ambiguous Correlation Fail Closed

如果：

```text
一个 invocation_identity_digest
→ 多个 approval lifecycle
```

不能：

```text
first-match
random-match
merge
```

然后 PASS。

而应该：

```text
ambiguous_identity_digests
→ FAIL / fail closed
```

因为错误匹配产生的 False PASS 比 BLOCKED 更危险。

------

# 42. Cross-run Isolation

```text
Run A Approval
```

不能使用：

```text
Run B TOOL_STARTED
```

作为证据。

Evidence envelope 强制：

```text
event.run_id == envelope.run_id
```

------

# 43. Synthetic Bad Case

为了验证 evaluator 不只是“会给正确系统打 PASS”，还构造：

```text
execution before approval
rejected then execution
duplicate execution
cancelled then execution
timeout then execution
correlation mismatch
```

要求：

```text
FAIL / BLOCKED
never PASS
```

------

# 44. Provenance

所有 Evidence 必须区分：

```text
REAL_LOCALAGENT_EVIDENCE

DETERMINISTIC_TEST_EVIDENCE

HYPOTHETICAL_BAD_CASE_FIXTURE
```

因此：

> Synthetic bad case 不能包装成真实 Runtime Bug。

这是整个项目真实性原则的重要组成部分。

------

# 45. 最终真实 E2E

Phase7 最有价值的真实链：

```text
AgentEvalOps Test
        ↓
LocalAgent subprocess
        ↓
FastAPI /api/chat
        ↓
ToolGovernanceService
        ↓
ToolApprovalController
        ↓
Desktop/UI contract independently covered
        ↓
HTTP approve/reject
        ↓
execution claim
        ↓
ToolExecutionService
        ↓
RunEventJournal
        ↓
safe Journal Evidence
        ↓
AgentEvalOps typed evaluator
        ↓
PASS / FAIL / BLOCKED
```

其中 Evaluation E2E 不依赖真实远端 LLM，使用 deterministic runtime/tool，以避免模型和网络随机性污染 HITL correctness。

------

# 46. Real Bad Cases — WP1

## 46.1 Empty risk_facts Journal Serialization

空 risk facts 与 Journal value constraints 冲突。

修复：

```text
empty
→ "NONE"
```

知识点：

> Event Payload 也必须符合 Persistence Contract。

------

## 46.2 Reject Double Step Terminal Commit

Approval owner 已经：

```text
WAITING → FAILED
```

completion owner 又尝试 commit terminal state。

知识点：

> Terminal State 必须只有一个 Owner。

------

## 46.3 Event Loop Ownership

同步 worker 调 ApprovalController 时没有 owner loop。

最终通过：

```text
owner loop
+
run_coroutine_threadsafe
```

解决。

知识点：

> Async State Ownership 往往与 Event Loop Ownership 绑定。

------

## 46.4 Weak Immutable Binding

只校验：

```text
invocation_id + tool_name
```

存在 Approval(A) → Execution(B) 风险。

最终加强完整 immutable binding。

知识点：

> TOCTOU。

------

# 47. Real Bad Cases — WP2

## 47.1 Streaming Test Transport Buffering

TestClient / ASGI transport 无法完成：

```text
读取 partial stream
→ HTTP approve
→ stream resume
```

最终采用：

```text
same-event-loop ASGI caller
```

同时标准 TestClient 保留：

```text
routing
validation
422
405
```

测试。

------

## 47.2 Generic AGENT_STEP_FAILED

Test router 缺少 method，

外层只看到统一 Adapter error。

知识点：

> Debug 多层 Runtime 时必须理解 Exception Translation。

------

## 47.3 Invalidated vs Idempotent

```text
approve
→ cancel
→ late approve
```

曾返回 200。

最终：

```text
invalidated priority
→ 410
```

知识点：

> Lifecycle validity > historical idempotency。

------

## 47.4 Illegal Test State

测试试图在同一个 Waiting Step 创建第二个 Approval，

状态机正确拒绝。

知识点：

> Bad Case Test 本身也必须遵守系统合法状态空间。

------

# 48. Real Bad Cases — WP3

## 48.1 actor_id_digest 被错误作为必填 Correlation

Audit metadata 与 Correlation field 混淆。

------

## 48.2 Aggregation Enum Bug

对 `AssertionStatus` 错误访问 `.status`。

------

## 48.3 NOT_APPLICABLE 参与聚合

导致本来 PASS 的 scenario 变 BLOCKED。

知识点：

```text
NOT_APPLICABLE != BLOCKED
```

------

## 48.4 Fake E2E Boundary

第一版 E2E 没进入真实 `ToolExecutionService`。

最终改用 WP2 HTTP Harness 和真实 Tool chain。

知识点：

> E2E 的可信度取决于实际穿过哪些 Production Boundaries。

------

## 48.5 Self-declared Trace Completeness

无条件：

```text
trace_complete=True
```

产生 False PASS 风险。

最终改为 terminal capture proof。

------

# 49. Real Bad Cases — WP4

## 49.1 Missing pyqtSignal Import

新增 ApprovalCardWidget 时遗漏 `pyqtSignal` import。

测试 collection 直接失败。

知识点：

> UI 改动也需要最基础的 import / collection smoke。

------

## 49.2 Test Fake 缺 Required Interface

旧 fake `chat_panel` 没实现 cleanup capability。

最初 production 使用 optional `getattr`。

Final Gate 改成：

```text
Production explicit required interface
+
Test fake follows production contract
```

知识点：

> Test Double 不应该反向削弱 Production Contract。

------

## 49.3 Terminal-vs-Late-HTTP Race Coverage Gap

Final Gate 补测：

```text
APPROVED
→ late HTTP network error
→ remains APPROVED
```

以及：

```text
INVALIDATED_TIMEOUT
→ late HTTP success
→ remains EXPIRED
```

知识点：

> 异步多通道系统必须明确 Authority Precedence。

------

## 49.4 Cross-run Cleanup Coverage Gap

补测：

```text
Run A terminal
→ Run A expired

Run B pending
→ unchanged
```

知识点：

> Scope ID 出现在状态 key 中时，应显式测试 Scope Isolation。

------

# 50. Phase7 最终已实现能力

## Runtime

```text
Risk-based Tool Approval
WAITING_FOR_APPROVAL
runtime-owned approval state
Approve / Reject
decision CAS
execution claim
single-process at-most-once
immutable invocation binding
cancel / timeout pre-claim safety
Journal-first approval evidence
```

## Transport

```text
TOOL_APPROVAL_REQUESTED streaming
TOOL_APPROVAL_DECIDED streaming
HTTP approve
HTTP reject
safe public DTO
binding digest correlation
HTTP idempotency
404 / 409 / 410 taxonomy
```

## UI

```text
Approval Card
tool/risk display
Approve / Reject buttons
background HTTP command
Qt signal/slot thread boundary
HTTP/stream race protection
Run-scoped cleanup
late callback safety
safe error presentation
```

## Evaluation

```text
typed HITL evidence
evidence completeness
PASS / FAIL / BLOCKED
correlation
cross-run isolation
cross-approval isolation
ambiguous correlation fail closed
Assertions A-F
synthetic bad cases
real LocalAgent → AgentEvalOps E2E
```

------

# 51. Phase7 未实现能力

仍然没有：

```text
Authentication
Authorization
RBAC

restart-safe pending recovery
graceful-shutdown resume

reconnect
event replay
approval status query

detached execution
durable workflow

approval center
approval history
notification

human-readable Tool argument summary

Plan Approval
Human Clarification

interactive AgentEvalOps HITL ExecutionTarget

HITL events in LocalAgent trace-export v1

distributed exactly-once
```

------

# 52. Phase7 Accepted P1

Phase 级去重后的 4 项：

```text
1. restart 不恢复 pending approval

2. graceful shutdown 不恢复 pending approval

3. client disconnect cancels active Run

4. approval waiting 消耗原 Run wall-clock deadline
```

这些是主动接受的工程边界，

不是遗漏后偷偷包装成完成。

------

# 53. 最终安全 Truth Boundary

必须始终明确：

```text
HTTP approve/reject implemented
!= authenticated approval

binding digest
!= authorization token

loopback deployment
!= authorization

single-process at-most-once
!= distributed exactly-once

Journal evidence
!= restart-safe executable recovery

Approval UI
!= production approval platform

Risk facts
!= complete human-readable side-effect summary
```

------

# 54. 测试 Truth

Phase7 各 Gate 实际测试范围包括：

```text
WP1 / WP2 Runtime focused tests
WP2 HTTP / Streaming tests
WP3 evaluator focused tests
WP3 AgentEvalOps relevant regression
LocalAgent approval focused smoke
WP4 UI / HTTP / stream focused tests
```

WP3 Final Gate：

```text
WP3 focused = 38 passed
AgentEvalOps relevant regression = 159 passed
LocalAgent approval smoke = 58 passed
```

WP4 Final Gate：

```text
UI/transport focused = 65 passed
compileall = PASS
git diff --check = PASS
```

未运行两个仓库完整 Full Repository Suite。

必须保留：

```text
FULL_REPOSITORY_SUITE_NOT_RUN
```

不能写：

```text
ALL TESTS PASS
```

------

# 55. 名词 / 概念速览

**HITL（Human-in-the-Loop，人在回路）**：在 Agent 关键操作中加入人工判断。

**Approval Gate（审批门禁）**：副作用发生前的 Human Decision Boundary。

**Runtime Owner（运行时所有者）**：拥有某类 Runtime State 最终解释权的组件。

**WAITING_FOR_APPROVAL（等待审批）**：Step 已开始执行，但当前等待人工决定的非终态。

**CAS（Compare-And-Set，比较并设置）**：只有当前状态符合预期时才能原子更新。

**Execution Claim（执行资格声明）**：批准后由唯一 worker 原子获得 Tool 执行资格。

**At-most-once（至多一次）**：目标操作最多执行一次。

**TOCTOU（检查时与使用时竞态）**：检查对象与真正使用对象在时间上发生变化。

**Immutable Binding（不可变绑定）**：将审批与冻结后的 Tool Invocation 严格关联。

**Journal-first（日记优先）**：业务状态生效前先成功记录权威事件。

**Fail Closed（失败关闭）**：无法确认安全时默认禁止执行。

**Observation Channel（观察通道）**：服务端向客户端传输 Runtime 事件。

**Command Channel（命令通道）**：客户端向 Runtime 提交变更命令。

**DTO（Data Transfer Object，数据传输对象）**：公共接口使用的专门数据结构。

**Presentation State（展示状态）**：只属于 UI 的视觉/交互状态。

**Runtime Truth（运行时事实）**：由 Runtime Authority 持有的业务事实。

**Qt Thread Affinity（Qt 线程亲和性）**：QObject 所属线程及其线程安全约束。

**Correlation（关联）**：证明多个 Event 属于同一个 Run / Approval / Invocation。

**Evidence Completeness（证据完整性）**：证明 Evaluation 使用的数据确实完整。

**BLOCKED（评估受阻）**：证据不足，无法判断 PASS 或 FAIL。

**Provenance（证据来源）**：说明 Evidence 来自真实 Runtime、测试还是合成场景。

**Synthetic Bad Case（合成坏案例）**：人为构造的错误事件序列，用来测试 Evaluator Detection Capability。

------

# 56. 工程构建方法类问答

## Q1：HITL Gate 应该放在哪里？

应该在：

```text
Tool Invocation 已经冻结
+
Governance 已经知道风险
+
Tool side effect 尚未发生
```

的位置。

------

## Q2：为什么 ToolGovernance 不直接等待 Human？

ToolGovernance 应负责：

```text
判断
```

而 ToolApprovalController 负责：

```text
等待和状态生命周期
```

避免 Policy Decision 与 Runtime Coordination 混在一起。

------

## Q3：为什么不能用 PENDING 表示等待审批？

因为 Step 已经被 Scheduler claim 并开始执行，

语义上已经不是 Pending。

------

## Q4：为什么 Run 仍然 RUNNING？

因为只有一个 Step 在等待，其他 sibling Step 可以继续。

------

## Q5：为什么 Approval 和 Execution Claim 分开？

前者表示：

```text
Human allows
```

后者表示：

```text
one worker may execute
```

解决并发和 duplicate execution。

------

## Q6：如何防止 Approval A 执行 Invocation B？

通过 immutable invocation binding，

在 execution claim 前再次验证冻结 Invocation。

------

## Q7：为什么 Journal-first？

没有持久化 Human Decision Evidence 时，

Tool 不应该获得执行资格。

------

## Q8：为什么 UI 点击 Approve 不能立即显示 Approved？

点击是：

```text
User Intent
```

不是：

```text
Runtime Fact
```

------

## Q9：HTTP 与 Stream 谁更权威？

HTTP 表达 command result，

stream 表达 Runtime lifecycle observation。

已经形成 terminal Runtime observation 后，

late HTTP result 不能覆盖它。

------

## Q10：为什么 HTTP 请求不能在 Qt UI Thread 运行？

否则网络延迟会阻塞 Qt Event Loop，导致界面冻结。

------

## Q11：Backend 已经幂等，为什么 UI 还禁用重复点击？

Backend Idempotency 是安全底线，

Frontend 防重复是 UX 与 Defense in Depth。

------

## Q12：为什么缺 TOOL_STARTED 不能直接 PASS？

因为可能是 Evidence 没采集完整。

------

## Q13：FAIL 与 BLOCKED 有什么区别？

FAIL：

```text
证据充分，行为确实违规
```

BLOCKED：

```text
证据不足，无法评价
```

------

## Q14：为什么需要 Synthetic Bad Case？

既要验证 evaluator 能识别正确，

也要证明它能发现错误。

------

## Q15：为什么当前不做 Restart Recovery？

那会进一步要求：

```text
persistent approval truth
scheduler reconstruction
worker continuation
event replay
reconnect
idempotency reconciliation
```

本质上开始进入 Durable Workflow Runtime。

当前面试 ROI 不值得在 Phase7 继续扩大。

------

# 57. 高频面试追问

## HITL / Runtime

1. 为什么 Agent 需要 HITL？
2. 哪些 Tool 应进入 Approval？
3. Approval Gate 应放在哪一层？
4. 谁拥有 Approval State？
5. 为什么 ToolGovernance 不负责等待？
6. 为什么新增 WAITING_FOR_APPROVAL？
7. 为什么 Run 仍然 RUNNING？
8. 为什么 WAITING 不能使用 PENDING？

## Concurrency / Safety

1. 两个 Approve 同时到达怎么办？
2. Approve 和 Reject race 怎么处理？
3. Approve 和 Cancel race 怎么处理？
4. Approval 为什么不能直接执行 Tool？
5. Execution Claim 解决什么？
6. 如何防 Duplicate Execution？
7. 什么是 TOCTOU？
8. 如何保证批准 A 最后执行的还是 A？

## Transport / API

1. 为什么 Streaming 和 HTTP Command 分离？
2. 为什么 Duplicate Approve 是 200？
3. 为什么 Conflict 是 409？
4. 为什么 inactive Run 是 410？
5. 为什么不暴露 raw invocation ID？
6. Binding Digest 为什么不是 Authorization Token？

## UI

1. 为什么 UI 不拥有 Approval Truth？
2. HTTP result 和 Stream event 如何合并？
3. 为什么 Terminal Stream Event 优先？
4. Qt 为什么不能在线程里直接更新 QWidget？
5. Late HTTP callback 怎么处理？
6. Run A Cleanup 如何不影响 Run B？
7. Backend 已幂等，为什么 UI 还要防 Double Click？
8. 为什么 Test Fake 不应该反过来削弱 Production Interface？

## Evaluation

1. 如何证明 Tool 在 Approval 后才执行？
2. Evidence Completeness 是什么？
3. 为什么没看到 TOOL_STARTED 不能自动 PASS？
4. PASS / FAIL / BLOCKED 有什么区别？
5. 如何防 Cross-run Evidence 串联？
6. Ambiguous Correlation 怎么处理？
7. Synthetic Bad Case 有什么价值？
8. 怎么证明 E2E 真正穿过 Production Boundary？

------

# 58. 30 秒面试总结

我在 LocalAgent 中实现了一套最小可信的 Tool Approval HITL。高风险 Tool 被 Governance 判为 `APPROVAL_REQUIRED` 后，Step 进入 `WAITING_FOR_APPROVAL`，Human Approve 并不会直接执行 Tool，而是由原 worker 原子取得 execution claim，从而解决 duplicate approve、approve/reject 和 cancel/timeout race；同时通过 immutable invocation binding 防止批准 A、实际执行 B。审批事件采用 Journal-first，并通过 Streaming 暴露给 PyQt Desktop Client，用户可以直接在 Approval Card 上批准或拒绝；HTTP 和 Stream 是两个异步通道，因此 UI 还处理了 terminal-state precedence 和 Qt thread safety。最后 AgentEvalOps 基于 typed evidence 验证 approval-before-execution、reject-zero-execution、at-most-once 和 evidence completeness，用 PASS / FAIL / BLOCKED 防止缺失证据产生假 PASS。

------

# 59. 2 分钟面试总结

Stage5-Phase7 主要解决 Agent 高风险 Tool 的 Human-in-the-Loop。

首先在 Runtime 层，我没有把 Approval 放到 Tool 内部，而是在 ToolInvocation 已冻结、Governance 已经判断出 `APPROVAL_REQUIRED`、但 ToolExecutionService 尚未产生真实副作用的位置加入 Approval Gate。Step 新增 `WAITING_FOR_APPROVAL`，但 Run 仍保持 RUNNING，因为其他 sibling Step 仍可能继续。

Approval state 由 run-scoped ToolApprovalController 统一管理。Human Approve 只进入 APPROVED，不会直接执行 Tool，原 worker 还要原子取得 `EXECUTION_CLAIMED` 才能调用 Tool，因此重复 Approve 不会产生第二次副作用。Cancel 或 Timeout 如果发生在 claim 前同样能阻止执行。Final Gate 还发现过一个真实 TOCTOU 风险：最初 claim 只校验 invocation ID 和 tool name，理论上可能批准 A、执行 B，所以后来加强为 args、idempotency key、resource key 等 immutable digest 的完整绑定。

第二步是 Transport。Runtime 的 `TOOL_APPROVAL_REQUESTED` 和 `TOOL_APPROVAL_DECIDED` 通过已有 `/api/chat` stream 发给客户端，Human Decision 使用独立 approve/reject HTTP endpoint 传回。公共 API 不暴露 raw invocation ID，而通过 run ID、approval ID 和 invocation binding digest 做 correlation。这里我明确区分 correlation 和 authorization，目前 Authentication / RBAC 没有实现。

之后补了 PyQt Desktop Approval Card。用户在聊天 timeline 里直接看到 tool name、risk level 和 risk facts，然后批准或拒绝。UI 只维护 presentation state，不复制 Runtime state machine；HTTP request 在线程中执行，通过 Qt signal 回 UI thread。因为 HTTP 与 Stream 是两个异步通道，还处理了 stream terminal state 与 late HTTP callback 的 race，例如 Runtime 已经 timeout 后，即使 late HTTP success 到达也不能把 EXPIRED 改回 APPROVED。

最后在 AgentEvalOps 中做 typed HITL evaluation。Evaluator 验证 Approval 必须发生在 Tool execution 前、Reject/Cancel/Timeout 后不得执行、Approve 后最多执行一次，并对 cross-run 和 ambiguous correlation fail closed。这里最重要的是 Evidence Completeness：没看到 `TOOL_STARTED` 不能说明 Tool 没执行，所以 incomplete trace 必须 BLOCKED。Final Gate 还真实发现过无条件 `trace_complete=True` 会产生假 PASS，因此最终只有完整读取 Journal 到真实 terminal `RUN_COMPLETED` 后才能声明 evidence complete。

最终 Phase7 是 `PASS_WITH_ACCEPTED_LIMITATIONS`。当前是 Minimum Credible Tool Approval HITL + Human-facing UI Closure，不包含 Authentication/RBAC、Restart Recovery、Reconnect、Durable Workflow 或 distributed exactly-once。

------

# 60. 最值得面试重点讲的五个设计

如果时间有限，优先讲：

## 1. Approval ≠ Execution Claim

体现：

```text
并发控制
状态机
副作用安全
幂等
```

## 2. Immutable Invocation Binding

体现：

```text
TOCTOU
安全边界
Approval Integrity
```

## 3. Journal-first

体现：

```text
Auditability
Fail Closed
Side-effect Authorization
```

## 4. HTTP / Stream Race + UI Terminal Wins

体现：

```text
异步系统
Qt Thread Safety
Presentation vs Runtime Truth
```

## 5. Evidence Completeness + BLOCKED

体现：

```text
Agent Evaluation
可信证据
避免 False PASS
```

这五个点已经足够把 Phase7 从“加了人工按钮”提升成一套完整的 Agent Runtime Safety 工程故事。

------

# 61. 简历技术表达参考

可以进一步压缩成：

> 基于风险治理实现 Tool Approval HITL，设计 Runtime-owned Pending/Approve/Reject 生命周期、CAS 与原子 Execution Claim，通过 Immutable Invocation Binding 防止审批后调用漂移；结合 Journal-first Event、Streaming + HTTP Command Transport 和 PyQt Approval Card 完成人工审批闭环，并在 AgentEvalOps 中以 Typed Evidence、Correlation 与 Evidence Completeness 验证 Approval-before-execution、Reject/Cancel/Timeout Safety 与 At-most-once。

正式简历仍应根据篇幅再压缩。

------

# 62. 最终项目叙事

不要把 Phase7 记成：

> “我给 Agent 加了两个批准/拒绝按钮。”

应该记成：

> **我从 Tool Governance、Runtime State Ownership、Step State Machine、Human Decision CAS、Execution Claim、Immutable Invocation Binding、Journal-first Evidence、HTTP/Streaming Transport、PyQt Human Interaction 和 AgentEvalOps Evidence Evaluation 十个层面，把原来只能拒绝高风险 Tool 的 Agent Runtime 演进成了一个可人工控制、可观察、可验证的最小可信 Tool Approval HITL。**

而且整个 Phase 始终保留明确 Truth Boundary：

```text
Minimum Credible Tool Approval HITL
+
Human-facing UI Closure

!=

Production Approval Platform
```

这是 Phase7 最终最可信、也最适合面试的工程叙事。