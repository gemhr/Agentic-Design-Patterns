# Stage5-Phase7-WP1 学习 / 面试总结

## Tool Approval Runtime Core（工具审批运行时核心）

WP1 最终状态：

```text
WP1_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS
BLOCKING_P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 4
ARCHITECTURE_REOPEN_REQUIRED = NO
READY_FOR_WP2 = YES
```

Codex Final Gate 已确认核心 Tool Approval、single-process execution claim、Journal evidence、Cancel/Timeout race 和线程 / Event Loop 边界全部通过。

------

# 1. 本 WP 解决什么问题

## 1.1 原问题

WP1 开始前，LocalAgent **其实已经有一个很像 HITL 的机制，但它不是真正的 HITL**。

已有链路是：

```text
Tool Invocation
    ↓
ToolGovernanceService
    ↓
风险判断
    ↓
APPROVAL_REQUIRED
    ↓
ToolGovernanceError
    ↓
工具不执行
```

例如一个高风险、非幂等、本地修改型 Tool 会被判定：

```text
APPROVAL_REQUIRED
```

但是系统只是：

> “这个动作需要审批，所以我拒绝执行。”

不存在：

```text
等待人工
→ 人工批准
→ 继续执行
```

所以它本质是：

> **Risk-based Denial Gate（基于风险的拒绝门禁）**

而不是：

> **Human-in-the-Loop（人在回路）**

Codex 源码审计明确确认：当时没有 Pending Human State、Approve/Reject command、Resume 或跨进程 continuation。

------

## 1.2 为什么值得解决

Agent 和普通 Chatbot 最大的区别之一，是 Agent 会：

```text
理解
→ 规划
→ 调用 Tool
→ 产生真实副作用
```

例如：

```text
删除文件
修改配置
操作数据库
创建工单
执行脚本
调用有写副作用的 API
```

如果所有动作都直接执行：

```text
LLM 判断失误
Prompt Injection
Tool 参数错误
Planner 错误
用户意图被误解
```

都可能直接转化成真实副作用。

但如果所有 Tool 都人工审批：

```text
Agent 自动化价值
≈ 0
```

所以工程上真正重要的是：

> **只在风险边界处插入人工决策。**

LocalAgent 已经有：

```text
risk classification
idempotency metadata
side-effect classification
ToolGovernanceService
```

所以 WP1 没有重新造风险体系，而是把已有：

```text
APPROVAL_REQUIRED
```

从“拒绝执行”升级成了“等待人工”。

------

## 1.3 WP1 最终解决到什么边界

现在真实链路是：

```text
High-risk ToolInvocation
        ↓
ToolGovernanceService
        ↓
APPROVAL_REQUIRED
        ↓
ToolApprovalController
        ↓
创建 ApprovalRequest
        ↓
Step:
RUNNING
→ WAITING_FOR_APPROVAL
        ↓
人工决定
   ┌────┴────┐
APPROVE    REJECT
   ↓           ↓
APPROVED     FAILED
   ↓       TOOL_APPROVAL_REJECTED
Execution       ↓
Claim        zero side effect
   ↓
EXECUTION_CLAIMED
   ↓
原 ToolInvocation
   ↓
ToolExecutionService
```

关键点不是“增加了 approve 按钮”。

而是建立了：

> **Runtime-owned Human Decision Lifecycle（由 Runtime 拥有的人工决策生命周期）**

以及：

> **Approval Decision 和 Tool Execution 之间的安全边界。**

------

# 2. 真实架构 / 数据流 / 状态流

## 2.1 Owner Boundary（所有权边界）

WP1 最重要的架构成果，其实是 Owner 划分。

```text
ToolGovernanceService
        │
        │ 判断 Risk
        ▼
ALLOW / DENY / APPROVAL_REQUIRED
        │
        ▼
AgentRouter
        │
        │ 遇到 APPROVAL_REQUIRED
        ▼
ToolApprovalController
        │
        ├─ ApprovalRequest
        ├─ Pending Truth
        ├─ Approve / Reject
        ├─ Decision CAS
        ├─ Wait / Wakeup
        └─ Execution Claim
```

同时：

```text
AgentState
   ↓
Step lifecycle truth

AgentStateMachine
   ↓
唯一合法 Step 状态修改入口
```

而：

```text
RunCoordinator
```

仍然是：

> **Run Terminal Owner（Run 终态所有者）**

没有因为 HITL 把整个 Runtime 所有权重新洗牌。

------

## 2.2 各组件到底负责什么

### ToolGovernanceService

只负责：

```text
这个 Tool 可不可以执行？
这个 Tool 是否需要人工批准？
```

即：

```text
ALLOW
DENY
APPROVAL_REQUIRED
```

它**不负责**：

```text
等人工
保存 approval
接收 approve
执行 Tool
```

这是非常重要的 Single Responsibility（单一职责）边界。

------

### ToolApprovalController

每个 active Run 一个：

```text
run-scoped ToolApprovalController
```

负责：

```text
pending truth
decision
CAS
execution claim
wait / wakeup
```

但它不负责：

```text
Risk classification
Tool execution
HTTP
Recovery
Snapshot
Scheduler
```

因此它没有变成万能的：

```text
ApprovalManager
```

Codex Final Gate 也专门检查了 `approval.py` 虽然已经超过 1000 行，但职责仍然围绕 run-scoped approval lifecycle，没有发生明显架构漂移。

------

### AgentRouter

Router 是 Tool Approval 的 **Interception Boundary（拦截边界）**。

原来：

```text
evaluate_invocation()
→ APPROVAL_REQUIRED
→ raise error
```

现在：

```text
evaluate_invocation()
→ APPROVAL_REQUIRED
→ request approval
→ wait
→ claim
→ execute
```

Router 不保存 approval truth。

------

### AgentState / StateMachine

增加了：

```text
StepStatus.WAITING_FOR_APPROVAL
```

但是没有增加：

```text
RunStatus.WAITING
RunStatus.PAUSED
RunStatus.PENDING_APPROVAL
```

这是一个非常值得面试讲的设计。

因为等待人工的是：

> 一个 Step。

而整个 Run：

```text
可能还有其他 sibling step 正在执行
```

所以：

```text
Run = RUNNING
Step = WAITING_FOR_APPROVAL
```

比：

```text
Run = PAUSED
```

更准确。

------

# 3. 核心设计选择 / 候选方案 / 取舍

# 3.1 为什么选择 Tool Approval，而不是 Plan Approval

候选方案其实至少有三种：

```text
Plan Approval
Tool Approval
Human Clarification
```

WP1 只做 Tool Approval。

原因是当前架构天然已经有：

```text
ToolInvocation
ToolExecutionSpec
Risk classification
Idempotency
Side-effect classification
Governance
```

而且 Tool 副作用边界非常明确。

因此：

```text
投入较小
+
面试价值高
+
安全意义强
+
容易测试
```

Plan Approval 则意味着要处理：

```text
整个 Plan 的 identity
Plan mutation
scheduler start boundary
multi-agent DAG
```

Human Clarification 又涉及：

```text
追加用户输入
conversation continuation
ContextBuilder
same-run vs new-turn
```

明显更大。

所以 Phase7 收敛到 Tool Approval 是正确的 Minimum Credible HITL 路线。

------

# 3.2 为什么 Approval Gate 不放在 Tool 内部

一种很直观但不好的方案是：

```text
Tool.invoke()
    ↓
if dangerous:
    ask human
```

问题在于：

不同 Tool 都要自己实现：

```text
Approval logic
Wait
Cancel
Timeout
Identity
Audit
```

容易产生：

```text
Tool A 有 gate
Tool B 忘了
Tool C gate 放在副作用之后
```

更严重的是：

> Tool 不应该拥有 Runtime lifecycle。

所以 WP1 把 gate 放在：

```text
ToolInvocation / ToolExecutionSpec 已冻结
        ↓
Governance 已判定 APPROVAL_REQUIRED
        ↓
ToolExecutionService 尚未开始
```

这一层。

这是一个典型的：

> **Pre-Side-Effect Boundary（副作用前边界）**。

------

# 3.3 为什么不直接在 `before_side_effect()` 等人工

LocalAgent 本来已经有：

```text
ToolExecutionContext.before_side_effect()
```

它离真实 commit 更近。

看起来似乎很适合。

但如果放在那里，Approval 发生时：

```text
Tool attempt 已创建
TOOL_STARTED 可能已经发生
budget/resource 可能已经预留
ToolAdapter 已经进入执行路径
```

而且每个 adapter 都必须正确调用：

```text
before_side_effect()
```

因此它更适合作为：

```text
Cancellation / Deadline / Side-effect evidence boundary
```

而不是 Human Approval Owner。

------

# 3.4 为什么不增加 RunStatus.PAUSED

因为：

```text
一个 Step 在等审批
```

不代表整个 Run：

```text
停止运行
```

例如：

```text
       Step A ───── WAITING_FOR_APPROVAL
      /
Plan
      \
       Step B ───── RUNNING → SUCCEEDED
```

所以：

```text
RunStatus = RUNNING
```

更符合实际。

如果设置：

```text
RunStatus.PAUSED
```

就会产生语义冲突：

> Run 到底是在暂停，还是正在执行 Step B？

------

# 3.5 为什么 WAITING Step 不退回 PENDING

因为 `PENDING` 在现有 Scheduler 中已经有明确语义：

> 这个 Step 还没有被 Scheduler claim。

而人工审批发生的时候：

```text
Step 已经被 claim
Worker 已经启动
Planner / Agent 已经生成 ToolInvocation
```

所以退回：

```text
PENDING
```

会破坏状态语义。

正确状态是：

```text
RUNNING
→ WAITING_FOR_APPROVAL
→ RUNNING
```

这也是为什么 WP1 不需要重写 Scheduler。

------

# 3.6 为什么 worker 在等待期间继续占 slot

这是一个明显的工程 trade-off（取舍）。

当前方案：

```text
Worker
→ WAITING_FOR_APPROVAL
→ await decision
→ 仍占 worker slot
```

另一种更“高级”的方案是：

```text
suspend worker
release slot
persist continuation
future resume
```

但后者马上涉及：

```text
generic suspension
requeue
continuation
scheduler resume
persistent workflow
```

复杂度高很多。

所以 WP1 有意接受：

> 一个等待审批的 worker 会占据当前 worker slot。

这是 Minimum Credible HITL，而不是 Durable Workflow Engine（持久工作流引擎）。

------

# 4. Approval 和 Execution Claim 为什么必须分离

这是 WP1 最值得深入理解的知识点之一。

错误方案：

```text
approve()
    ↓
execute tool
```

问题是如果：

```text
请求 A：approve
请求 B：approve
```

并发到达：

两个请求都可能：

```text
execute()
```

导致副作用执行两次。

所以 WP1 做成：

```text
PENDING
    ↓
APPROVED
    ↓
原 worker 醒来
    ↓
claim_execution()
    ↓
EXECUTION_CLAIMED
    ↓
execute
```

关键是：

```text
APPROVED
```

表示：

> 人类已经同意。

而：

```text
EXECUTION_CLAIMED
```

表示：

> 已经有唯一 worker 获得了把这次批准转化为 Tool Execution 的资格。

这两个状态完全不是一回事。

------

## 4.1 用数据库事务思维理解

可以把它类比成：

```text
APPROVED
≈ business authorization

EXECUTION_CLAIMED
≈ atomic lease / lock acquisition
```

批准是一条业务事实。

Claim 是一次执行协调事实。

------

## 4.2 为什么这不是 distributed exactly-once

WP1 使用：

```text
single-process
asyncio.Lock
run-scoped controller
```

保证：

```text
同一个 active process
同一个 approval
最多一个 execution claim
```

但如果：

```text
进程崩溃
网络分区
多副本 Runtime
```

当前没有分布式协调。

因此准确表述是：

> single-process at-most-once execution claim

而不是：

> distributed exactly-once execution。

Codex Final Gate 专门把这条 Truth Boundary 固定下来了。

------

# 5. CAS（Compare-And-Set，比较并设置）如何处理审批竞争

审批最大的危险不是 happy path。

而是 Race Condition（竞态条件）。

------

## 5.1 Duplicate Approve

场景：

```text
APPROVE A
APPROVE B
```

几乎同时到。

正确行为：

```text
第一个：
PENDING → APPROVED

第二个：
发现已经 APPROVED
→ 返回 idempotent success
```

但是：

```text
execution claim
```

仍只有一次。

所以：

```text
重复批准
≠
重复执行
```

------

# 5.2 Approve vs Reject

```text
APPROVE
   ↘
    PENDING
   ↗
REJECT
```

规则：

> First successful decision wins（第一个成功决策获胜）

例如：

```text
APPROVE first
→ APPROVED

REJECT later
→ APPROVAL_DECISION_CONFLICT
```

绝不能出现：

```text
Journal = APPROVED
Controller = REJECTED
```

这种 Split Truth（事实分裂）。

------

# 5.3 Approve vs Cancel

最危险的窗口是：

```text
APPROVED
     ↓
尚未 EXECUTION_CLAIMED
```

如果这时候 Run 被 Cancel：

正确设计是：

```text
APPROVED
+
Cancellation
        ↓
Execution Claim 再次检查 CancellationToken
        ↓
claim rejected
        ↓
Tool zero execution
```

所以：

> Approve 并不是不可撤销的 Tool Execution。

只要执行资格还没有 claim，Runtime lifecycle 仍可以阻止它。

------

# 5.4 Approve vs Timeout

同理：

```text
APPROVED
        ↓
deadline expired
        ↓
claim_execution()
        ↓
检查 deadline
        ↓
fail
```

因此 late approval 不能突破 Runtime deadline。

------

# 6. Immutable Invocation Binding（不可变调用绑定）

这是 Codex Final Gate **真实发现并修复**的一个 Bad Case。

原实现中 execution claim 主要验证：

```text
invocation_id
+
tool_name
```

问题是假如内部错误构造出：

```text
原 Invocation:
id = 123
tool = update_config
args = A
```

但 claim 时换成：

```text
伪 Invocation:
id = 123
tool = update_config
args = B
```

如果只检查：

```text
ID + tool name
```

那么 B 可能利用对 A 的 Approval。

这就是典型：

> **TOCTOU（Time-of-Check to Time-of-Use，检查时与使用时不一致）**

审批时检查的是：

```text
Invocation A
```

真正执行的却可能变成：

```text
Invocation B
```

Codex Gate 将 claim 校验扩展到完整 frozen binding，包括：

```text
invocation id
tool name
arguments digest
idempotency-key digest
resource-key digest
```

所以：

```text
Approval(A)
```

只能授权：

```text
Execution(A)
```

不能授权：

```text
Execution(B)
```

这是 WP1 最值得作为真实面试 Bad Case 讲的案例之一。

------

# 7. Journal-first（日志优先）为什么重要

普通系统可能：

```text
先把状态改成 APPROVED
        ↓
再写日志
```

问题是：

如果日志写失败：

```text
Runtime:
APPROVED

Journal:
PENDING
```

这意味着：

> 工具可能执行了，但你没有可信证据证明它是经过批准的。

对于 HITL，这是严重问题。

所以 WP1 保持已有：

> **Journal-first**

原则。

------

## 7.1 Approval Request

必须：

```text
Journal:
TOOL_APPROVAL_REQUESTED
        ↓
成功
        ↓
Pending 对 Runtime 生效
```

如果写失败：

```text
Fail Closed
```

绝不能 Tool Execution。

------

## 7.2 Approval Approved

```text
TOOL_APPROVAL_DECIDED(APPROVED)
        ↓
Journal 成功
        ↓
APPROVED 成为 effective truth
        ↓
execution claim
```

因此关键 invariant（不变量）是：

```text
TOOL_APPROVAL_REQUESTED
<
TOOL_APPROVAL_DECIDED(APPROVED)
<
TOOL_STARTED
```

Final Gate 已实际验证这一 ordering。

------

## 7.3 Reject

```text
TOOL_APPROVAL_DECIDED(REJECTED)
        ↓
Step FAILED
```

并必须满足：

```text
REJECTED
=> no TOOL_STARTED
```

这就是非常典型的：

> Safety Invariant（安全不变量）。

------

# 8. Cancellation、Reject、Timeout 三者有什么区别

这是 HITL 高频面试题。

## Reject

语义是：

> 人明确不同意这一个 Tool action。

所以：

```text
WAITING_FOR_APPROVAL
→ FAILED
```

错误原因：

```text
TOOL_APPROVAL_REJECTED
```

但 Reject：

```text
!= Cancel Run
```

------

## Cancel

语义是：

> 整个 Run 不应该继续。

来源可能是：

```text
用户主动 Cancel
Client Disconnect
Graceful Shutdown
```

因此它属于：

```text
Run lifecycle
```

而不是：

```text
Human approval decision
```

------

## Timeout

语义是：

> Run 生命周期超出了 deadline。

WP1 没有引入：

```text
approval-specific timeout clock
```

而是继续使用现有：

```text
Run wall-clock deadline
```

这也是刻意降低架构复杂度。

------

# 9. Thread / Event Loop 边界

这也是实施中真实发现的问题。

LocalAgent 的部分 Tool execution 路径在：

```text
同步 worker thread
```

而 `ToolApprovalController` 依赖：

```text
asyncio event loop
```

最初实现遇到了：

```text
ApprovalError:
controller 未绑定 Event Loop
```

根因是：

```text
sync worker
```

不能直接假设自己运行在 owner event loop 上。

最后实现采用：

```text
ToolApprovalController(loop=...)
```

以及类似：

```text
run_coroutine_threadsafe
```

把 mutation 投递回 Run 的 owner loop。

------

## 为什么这很危险

如果设计错误可能产生：

```text
wrong loop
deadlock
permanent waiter
loop closed
Future 永远不完成
```

所以 Codex Final Gate 专门检查：

```text
owner loop command
sync worker thread
controller close
cancellation wakeup
run finalization
```

并确认 focused tests 中没有出现 deadlock 或 orphaned waiter。

------

# 10. 真实性与完成边界

## 已实现

```text
Risk-based Tool Approval interception

run-scoped ToolApprovalController

ApprovalRequest / ApprovalDecision

PENDING / APPROVED / REJECTED

WAITING_FOR_APPROVAL Step

APPROVE domain command

REJECT domain command

single-process atomic decision

single-process execution claim

duplicate approve protection

approve/reject race handling

approve/cancel race handling

approve/timeout race handling

immutable invocation binding

Journal approval events

safe approval payload

model self-approval protection
```



------

## 已测试

Final Gate 重新执行：

```text
WP1 focused:
55 passed
4 subtests passed
```

相关 Runtime 回归：

```text
210 passed
27 subtests passed
3 warnings
```

以及：

```text
compileall PASS
git diff --check PASS
```

没有运行全部 3127 collected tests，因此不能说：

```text
全仓测试全部通过
```



------

## Accepted P1

共 4 项：

### 1. Restart 不恢复 Pending

```text
server restart
→ pending approval 不恢复
```

------

### 2. Graceful Shutdown 不恢复 Pending

shutdown 后：

```text
不会继续原 approval / execution
```

------

### 3. Client Disconnect 会 Cancel Run

因为当前 HTTP/Streaming 仍是 request-owned。

------

### 4. Approval Wait 消耗原 Run Deadline

没有：

```text
pause timeout clock
```



------

## Accepted Limitation

目前没有：

```text
HTTP approve/reject transport
Approver Authentication
RBAC
Multi-Approver
Plan Approval
Human Clarification
Detached Execution
Distributed Exactly-once
```

------

## Future

```text
restart-safe continuation
Snapshot restore approval
Recovery replay
durable workflow
HTTP/API
AgentEvalOps HITL evaluation
```

------

# 11. Real Bad Cases

## Bad Case 1 — 空 risk_facts 无法写 Journal

**真实性：IMPLEMENTATION_DISCOVERY**

### Trigger

Approval event 的：

```text
risk_facts
```

为空。

### Symptom

Journal 拒绝：

```text
"" 
```

因为 safe journal string 要求非空。

### Root Cause

空集合直接被序列化成空字符串。

### Fix

稳定编码成：

```text
"NONE"
```

### Knowledge Point

> 安全事件 Schema 不只是“字段类型对”，还必须满足持久化层的值域约束。



------

# Bad Case 2 — Reject 导致二次 Step Commit

**真实性：TEST_FAILURE**

### Trigger

Tool 被人工 Reject。

### Symptom

出现：

```text
STEP_STATE_COMMIT_FAILED
```

### Root Cause

Step 已经因为：

```text
WAITING → FAILED
```

进入终态。

但 worker 又以普通字符串 result 返回，completion owner 再次尝试 commit Step。

形成：

> Two Owners attempting terminalization（两个组件同时尝试终结状态）。

### Fix

Reject 时：

```text
ToolApprovalRejectedError
```

向 executor boundary 上抛。

由 executor 幂等收口。

### Knowledge Point

> Terminal State（终态）必须有唯一 Owner，否则很容易出现 double commit。

这是非常好的 Runtime 面试案例。

------

# Bad Case 3 — Controller 没有绑定 Event Loop

**真实性：IMPLEMENTATION_DISCOVERY**

### Trigger

同步 worker thread 发起 Approval Request。

### Symptom

```text
controller 未绑定 Event Loop
```

### Root Cause

审批状态由 async owner loop 管理，但 Tool path 可能处于 sync worker。

### Fix

显式：

```text
controller owner loop
+
run_coroutine_threadsafe
```

### Knowledge Point

> 在 Async Runtime 中，State Ownership（状态所有权）往往同时意味着 Event Loop Ownership（事件循环所有权）。



------

# Bad Case 4 — Approval 对错误 Invocation 生效

**真实性：CODEX FINAL GATE DISCOVERY**

这是本 WP 最有价值的真实 Bad Case。

### Trigger

构造：

```text
same invocation_id
same tool_name
```

但是替换：

```text
args
idempotency key
resource key
```

### Risk

人工批准：

```text
Invocation A
```

最终却执行：

```text
Invocation B
```

这等价于绕过 HITL。

### Root Cause

claim 绑定过弱，只验证：

```text
invocation_id + tool name
```

### Fix

Execution Claim 校验：

```text
invocation id
tool name
arguments digest
idempotency-key digest
resource-key digest
```

### Regression

Codex 增加三类：

```text
same ID
+
replacement args

same ID
+
replacement idempotency key

same ID
+
replacement resource key
```

均不能 claim。

### Knowledge Point

```text
Approval identity
必须绑定
真正执行对象的 immutable snapshot
```

这也是：

> TOCTOU（Time-of-Check to Time-of-Use）问题在 Agent Tool Approval 场景中的真实体现。



------

# 12. 名词 / 概念速览

**HITL（Human-in-the-Loop，人在回路）**：Agent 在关键执行边界暂停自动行为，引入人工决策。

**Approval Gate（审批门禁）**：在高风险动作真正产生副作用之前要求人工批准的控制点。

**Tool Governance（工具治理）**：根据风险、权限、幂等性和副作用属性决定 Tool 是否允许执行。

**Side Effect（副作用）**：对文件、数据库、远端系统等真实外部状态产生改变。

**Fail Closed（失败关闭）**：系统无法确认安全条件时默认拒绝执行，而不是放行。

**Runtime Owner（运行时所有者）**：负责某类运行状态及其合法生命周期变化的组件。

**Pending Approval（待审批）**：Tool 已被识别为需要人工批准，但人工尚未作出决定。

**Execution Claim（执行资格声明）**：批准完成后由唯一 worker 原子取得实际执行该 invocation 的资格。

**CAS（Compare-And-Set，比较并设置）**：仅当状态仍为预期旧值时才能原子更新状态，用于处理并发竞争。

**Immutable Invocation（不可变调用）**：审批后不可再更改参数、Tool identity 等执行事实的 Tool 调用描述。

**Invocation Binding（调用绑定）**：把 Approval 与具体 immutable ToolInvocation 强关联，防止批准 A、执行 B。

**Idempotency（幂等性）**：同一操作重复执行多次仍不会产生额外状态变化。

**Journal-first（日志优先）**：业务状态成为有效事实前先成功写入权威审计事件。

**Safety Invariant（安全不变量）**：无论并发或失败路径如何变化，都必须始终成立的安全条件。

**TOCTOU（Time-of-Check to Time-of-Use）**：检查对象与实际使用对象之间被替换或发生变化导致的安全问题。

**Race Condition（竞态条件）**：多个并发操作因为执行顺序不同而可能产生不同甚至错误结果。

**Run-scoped（Run 作用域）**：对象生命周期和数据只属于某一个 Run，不跨 Run 共用。

**At-most-once（至多一次）**：一次逻辑操作最多执行一次，也可能一次都不执行。

**Durable Workflow（持久工作流）**：即使进程退出或服务重启，也可以恢复未完成 Workflow 的系统。

------

# 13. 工程构建方法类问答

## Q1：为什么不直接让 `ToolGovernanceService` 管人工审批？

因为它当前负责：

```text
Risk / Policy Evaluation
```

如果继续让它负责：

```text
Pending
Decision
Wait
Execution Claim
```

就会把：

```text
Policy Engine
```

变成：

```text
Workflow Runtime
```

职责耦合。

正确分工：

```text
ToolGovernanceService
→ 是否需要 Approval

ToolApprovalController
→ Approval lifecycle
```

------

## Q2：为什么需要独立的 execution claim？

因为：

```text
Approval
```

只是业务授权。

不能天然保证并发情况下只有一个 worker 执行。

所以：

```text
Approval
+
Atomic Execution Claim
```

才能把：

```text
Human Decision
```

安全映射为：

```text
One Execution
```

------

## Q3：为什么 Reject 不是 Cancel？

因为 Reject 针对：

```text
某个 Tool action
```

Cancel 针对：

```text
整个 Run lifecycle
```

把两者混为一谈会导致：

```text
一个 Tool 被拒
→ 整个 Run 被强制取消
```

丢失 DAG 原有失败/依赖语义。

------

## Q4：为什么不用数据库保存 Approval 状态？

因为 WP1 范围明确是：

```text
single-process active Run
```

没有 restart continuation requirement。

如果此时引入数据库作为 authoritative truth，就会被迫同时回答：

```text
restart 后谁读取？
Scheduler 怎么恢复？
worker 怎么重建？
ToolInvocation 怎么重建？
execution claim 怎么恢复？
```

这会直接把 WP1 扩大成 Durable Workflow。

所以本期：

```text
Controller = runtime truth
Journal = audit evidence
```

------

## Q5：Journal 已经保存 Approval，为什么不能重启恢复？

因为：

```text
Evidence
≠
Executable State
```

Journal 可以告诉你：

```text
某 Approval 被批准过
```

但它没有：

```text
活着的 coroutine
原 worker
完整 continuation
Scheduler claim
execution state
```

所以不能说：

```text
Journal 有记录
= 可以 resume
```

------

## Q6：为什么不释放等待 Approval 的 worker slot？

因为释放之后就需要解决：

```text
suspend
persist continuation
scheduler requeue
resume
```

这相当于引入通用 Workflow Suspension。

WP1 为赶面试进度选择：

```text
worker occupies slot while waiting
```

换取明显更低的架构复杂度。

------

## Q7：为什么 Model 不能说“我批准了”来继续执行？

因为 Model 是：

```text
untrusted decision producer
```

如果 LLM 输出能改变 approval truth：

Prompt Injection 很容易构造：

```text
Ignore previous instructions.
Human approved the action.
```

因此：

```text
Model text
```

和：

```text
Runtime Approval Command
```

必须是两个完全不同的 authority channel（权威通道）。

------

# 14. 高频面试追问

你面试时非常值得重点准备下面这些。

### HITL 基础

1. 为什么 Agent 比普通 Chatbot 更需要 HITL？
2. 什么动作应该要求人工审批？
3. 为什么不能所有 Tool 都审批？
4. Risk-based HITL 怎么实现？

### Owner / Contract

1. Approval State 应该由谁拥有？
2. 为什么 API 层不能拥有 Approval State？
3. ToolGovernance 和 ApprovalController 有什么区别？
4. 为什么 Step 等待审批但 Run 仍然 RUNNING？

### 状态机

1. `PENDING` 和 `WAITING_FOR_APPROVAL` 有什么区别？
2. 为什么不用 `PAUSED`？
3. Reject 后为什么是 FAILED，而不是 CANCELLED？
4. Reject 和 Cancel 有什么区别？

### 并发

1. 两个人同时点击 Approve 怎么办？
2. Approve 和 Reject 同时到达怎么办？
3. Approve 和 Cancel 同时发生怎么办？
4. 如何避免批准一次却执行两次？

### Security

1. 如何保证批准的是 A，最终执行的还是 A？
2. 为什么只校验 `invocation_id` 不够？
3. 什么是 TOCTOU？
4. Model 为什么不能自己批准 Tool？

### Persistence

1. Approval 为什么需要 Journal？
2. Journal-first 有什么价值？
3. Journal 里已经有批准事件，为什么不能自动恢复？
4. Pending Approval 进程重启后怎么办？

### Runtime

1. 一个 Step 等审批时其他 Step 怎么办？
2. 为什么等待期间 worker slot 没释放？
3. Timeout 在 Approval 期间怎么计算？
4. Client Disconnect 怎么处理？

------

# 15. 30 秒面试总结

> 我在 LocalAgent 里实现了一套最小可信的 Tool Approval HITL。项目原本已经能根据 Tool 风险、幂等性和副作用把高风险调用判定成 `APPROVAL_REQUIRED`，但之前只是直接拒绝，并没有真正的人机审批闭环。我把审批状态放在 Runtime-owned、run-scoped 的 `ToolApprovalController` 中，Step 增加 `WAITING_FOR_APPROVAL`，Run 仍保持 `RUNNING`。人工批准后不会直接执行 Tool，而是由原 worker 再通过原子 execution claim 获取一次性执行资格，从而处理 duplicate approve、approve/reject 和 cancel/timeout race。审批事件继续使用 Journal-first，保证 `APPROVAL_REQUESTED < APPROVED < TOOL_STARTED`。当前明确限制为单进程 active Run，不宣称支持 restart recovery 或 distributed exactly-once。

------

# 16. 2 分钟面试总结

> LocalAgent 原来已经有一套 Tool Governance，可以根据 Tool 的风险、是否本地修改以及幂等性判断 `ALLOW`、`DENY` 或 `APPROVAL_REQUIRED`。但 `APPROVAL_REQUIRED` 当时只是 fail-closed 地拒绝执行，并不是真正的 HITL。
>
> 我们在这一阶段把它扩展成了最小可信的 Tool Approval Runtime Core。架构上没有让 ToolGovernance 或 API 成为审批 Owner，而是在每个 active Run 内增加 run-scoped 的 `ToolApprovalController`，负责 Pending、Approve/Reject、并发 CAS、wait/wakeup 和 execution claim。Step 新增 `WAITING_FOR_APPROVAL`，但 Run 仍然保持 `RUNNING`，这样同一个 Run 中已经开始的 sibling step 仍然可以继续。
>
> 安全上最关键的一点是把 Approval Decision 和 Tool Execution 分开。人工 Approve 以后只进入 `APPROVED`，原 worker 还必须原子取得 `EXECUTION_CLAIMED` 才能调用 `ToolExecutionService`，所以重复 Approve 不会产生重复副作用。同时 cancel 或 timeout 如果在 claim 之前发生，会让后续 late approve 无法执行。
>
> 我们还保持了 Journal-first，审批 Request 和 Decision 成为有效事实之前必须先成功写 Journal，所以可以保证 `APPROVAL_REQUESTED < APPROVED < TOOL_STARTED`，Reject 后没有 `TOOL_STARTED`。
>
> 实施过程中有几个真实问题。一个是 Reject 后 Step 已经 FAILED，但普通 completion path 又尝试 terminal commit，导致 double commit；最终通过 typed rejection error 在 executor boundary 收口。另一个是同步 worker 和 async controller 的 Event Loop ownership 问题。Final Gate 又发现 execution claim 只校验 invocation ID 和 tool name 会产生 TOCTOU 风险，于是进一步把 approval 绑定到 arguments、idempotency key、resource key 等 immutable digest。
>
> 最终 WP1 是 `PASS_WITH_ACCEPTED_LIMITATIONS`，Blocking P1 为 0。我们明确没有实现 restart-safe continuation、RBAC 和 distributed exactly-once，因为那些会把这个阶段扩大成 Durable Workflow Runtime。这也是为了在工程可信度和实现成本之间做取舍。

------

# 17. 推荐你重点深入的关键词

如果只为了近期 AI Agent 社招，我建议这一 WP 往外扩展学习这些：

```text
Human-in-the-Loop
Approval Gate
Tool Governance
Policy Enforcement Point / Policy Decision Point

State Machine
State Ownership
Single Source of Truth

Optimistic Concurrency Control
Compare-And-Set
Race Condition
At-most-once
Exactly-once Semantics

Idempotency
TOCTOU

Journal-first
Event Sourcing
Audit Trail

Cancellation
Timeout
Cooperative Cancellation

Durable Execution
Workflow Engine
Temporal / Durable Functions 概念

Asyncio Event Loop
run_coroutine_threadsafe
Thread Safety
```

其中面试优先级最高的是：

```text
HITL
Tool Governance
State Machine
CAS
Idempotency
TOCTOU
Cancellation
Journal-first
Exactly-once vs At-most-once
```

------

# 18. 推荐学习文档文件名

```text
docs/interview/stage5_phase7_wp1_tool_approval_runtime_core.md
```

