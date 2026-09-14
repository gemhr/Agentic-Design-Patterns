# Stage7-WP2 — Durable HITL & Approval Recovery

## 一、本 WP 到底解决了什么问题

WP2 解决的核心问题不是“给 Agent 加一个确认按钮”，而是：

> 当 Agent 的高风险 Tool 需要人工审批时，审批状态如何脱离单进程内存，跨实例、跨进程存活，并且在恢复执行时仍能保证审批绑定、Run Ownership 和 Tool Execution Claim 都是安全的。

WP2 之前，Approval 的核心状态主要依赖 `ToolApprovalController` 和当前进程内的 waiter。

这种设计在单进程 Demo 中可以工作：

```text
Tool
→ APPROVAL_REQUIRED
→ 内存 pending
→ HTTP APPROVE
→ 唤醒 waiter
→ 执行 Tool
```

但多实例后马上出现问题：

```text
Run 在 instance A 等待审批

HTTP APPROVE 打到 instance B

B 没有 A 的 controller/waiter
```

或者：

```text
Run 等待审批
→ process crash
→ 内存 pending/waiter 消失
```

WP2 最终把真实生产链升级为：

```text
Tool Invocation
→ ToolGovernanceService
→ APPROVAL_REQUIRED
→ DurableApprovalService
→ PostgreSQL PENDING
→ WAITING_FOR_APPROVAL
→ authenticated HTTP APPROVE / REJECT
→ PostgreSQL first-wins decision
→ worker 从 durable authority 观察 decision
→ current Run fencing validation
→ durable execution claim
→ Tool continuation
```

REJECT 路径则保证零 Tool execution。

------

# 二、名词 / 概念速览

### 持久化审批（Durable Approval）

Approval 的 canonical truth 保存在 PostgreSQL，而不是某个进程中的 Python 对象。

### 人类在环（Human-in-the-Loop, HITL）

Agent 在执行高风险操作前暂停，让人类做出 APPROVE / REJECT 决策。

### 审批权威（Approval Authority）

决定某个 Approval 当前究竟是 `PENDING / APPROVED / REJECTED / INVALIDATED` 的唯一权威数据源。

WP2 中：

```text
PostgreSQL DurableApprovalService
```

才是 Approval Authority。

### Waiter

当前 worker 中等待审批结果的运行期对象，只负责等待和唤醒，不再保存审批真值。

### Facade

`ToolApprovalController` 仍然为 Runtime 提供原有接口，但内部真实状态由 DurableApprovalService 持有。

### 首胜语义（First-Wins）

APPROVE 与 REJECT 并发时，只有第一个成功提交的 decision 生效，之后不能反转。

### 幂等决策（Idempotent Decision）

同一个 APPROVE 重复提交时，不产生第二次状态转换，而是返回已有有效结果。

### 审批绑定（Approval Binding）

Approval 不是简单绑定一个 `approval_id`，而是绑定某一个确定的、不可变的 Tool Invocation。

### 调用绑定摘要（Invocation Binding Digest）

使用规范化数据生成的摘要，用来证明“人类批准的正是现在准备执行的这次调用”。

### 执行声明（Execution Claim）

审批通过之后，真正赋予某个合法 Executor“一次执行资格”的独立 durable 记录。

### 栅栏令牌（Fencing Token）

来自 WP1，用来保证失去 Run Ownership 的 stale executor 无法继续获得 Tool execution claim。

### `WAITING_APPROVAL`

Agent 已经产生需要审批的 Tool Invocation，并进入等待人工决策的运行边界。

### `APPROVED_PRE_EXECUTION`

人工已经批准，但 Tool 尚未真正开始执行的恢复边界。

### 审批失效（Invalidation）

当 Run 已取消、Deadline 已超时或 Run 已终止时，仍处于 PENDING 的 Approval 被标记为不可继续使用。

------

# 三、为什么“有 APPROVE API”不等于 Durable HITL

最简单实现：

```python
pending[approval_id] = invocation
```

HTTP：

```python
pending[approval_id].approve()
```

这种实现只能证明：

> 当前 Python 进程中，一个 HTTP 请求能修改另一个内存对象。

它没有回答：

```text
HTTP 请求落到另一个实例怎么办？
进程重启怎么办？
旧 executor 恢复怎么办？
APPROVE 和 REJECT 并发怎么办？
重复 APPROVE 怎么办？
批准以后进程崩溃怎么办？
Approval 对应的 Tool 参数被换掉怎么办？
```

所以真正的 Durable HITL 至少需要：

```text
Durable Approval State
+
Binding
+
First-Wins
+
Run Fencing
+
Execution Claim
+
Recovery Boundary
```

------

# 四、为什么 ToolApprovalController 不能继续做 Authority

WP2 之后：

```text
ToolApprovalController
```

仍然存在。

但角色已经变成：

```text
facade
+
waiter
+
local wakeup
```

而不是：

```text
approval truth
```

Final Gate 明确验证，生产链中的 Approval mutation 由 `DurableApprovalService` 负责，HTTP handler 直接向 durable service 提交 decision；Controller 只是观察 PostgreSQL Authority 并投影到本地等待状态。

这是一个很重要的后端设计思想：

> “保留内存对象”没有问题，问题在于不能让它同时成为分布式业务真值。

和 WP1 的 `RunRegistry` 很相似：

```text
RunRegistry
→ cache / wakeup

ToolApprovalController
→ facade / waiter / wakeup
```

真正 Authority 都已经迁移到 PostgreSQL。

------

# 五、Approval 为什么不能只保存 approval_id

错误模型：

```text
approval_id = 123
state = APPROVED
```

然后未来只要拿：

```text
approval_id=123
```

就执行当前 Tool。

问题是当前 Tool Invocation 可能已经变化：

```text
原审批：
transfer(amount=100)

后来：
transfer(amount=100000)
```

如果只认 approval_id：

可能出现：

> 人类批准的是 A，系统最后执行的是 B。

所以 Approval 必须绑定 immutable invocation。

WP2 的 binding 至少覆盖：

```text
run_id
step_id
invocation_id
canonical tool name

arguments digest
idempotency digest
resource digest
risk facts

invocation_binding_digest
```

Decision 和 Execution Claim 都必须校验同一份 canonical binding。Final Gate 明确确认 production continuation 不是只靠 `approval_id`。

------

# 六、为什么使用 Digest，而不是直接保存全部参数

一方面要证明：

```text
审批对象没有变化
```

另一方面 Tool 参数可能含：

```text
路径
业务数据
隐私字段
token
secret
```

不应该为了 Approval Binding 再复制一份完整敏感 payload。

所以常见设计是：

```text
canonical JSON
↓
SHA-256
↓
digest
```

Approval 保存 digest。

执行时重新 canonicalize 当前 Invocation，然后比较 digest。

这样兼顾：

```text
identity integrity
+
less sensitive duplication
```

------

# 七、为什么 APPROVE 和 REJECT 必须 First-Wins

考虑真实并发：

```text
管理员 A：APPROVE
管理员 B：REJECT
```

两请求几乎同时到达。

错误实现：

```text
UPDATE state = APPROVED

然后

UPDATE state = REJECTED
```

结果取决于谁最后写，Approval 可以被随意反转。

正确状态机：

```text
PENDING
 ├→ APPROVED
 └→ REJECTED
```

一旦离开 PENDING：

```text
不能再反向修改
```

WP2 的 `decide()` 在 PostgreSQL transaction 中锁定 approval row，因此首个 decision 获胜；同向重复 decision 幂等，反向 decision 返回 conflict。真实 PostgreSQL race test 已验证。

------

# 八、为什么 APPROVED 不能直接等于“可以执行 Tool”

这是 WP2 最重要的设计之一。

有两个完全不同的问题：

```text
1. 人类有没有授权？
2. 哪个 executor 有资格执行？
```

所以：

```text
Approval Decision
```

与：

```text
Execution Claim
```

必须分离。

例如：

```text
Approval = APPROVED
```

只表示：

> 人类批准了这一个 immutable invocation。

然后还需要：

```text
current Run owner
+
current fencing token
+
binding match
+
no previous claim
```

才能得到：

```text
durable execution claim
```

Final Gate 中 execution claim 在同一个 PostgreSQL transaction 内同时验证 current Run lease/fencing、Approval state 和 binding，然后插入唯一 claim。

------

# 九、为什么 Execution Claim 要独立持久化

考虑：

```text
APPROVED
```

以后两个 worker 同时醒来。

如果只判断：

```text
if approval == APPROVED:
    execute_tool()
```

那么两个都可能执行。

所以需要：

```text
runtime_tool_execution_claims
```

并对：

```text
approval_id
```

做唯一约束。

两个 executor 同时 claim：

```text
只有一个成功
```

这保证的是：

> 同一个 approved immutable invocation 只有一个合法执行资格。

注意，这仍然不是：

```text
external side effect exactly-once
```

它只解决：

```text
pre-execution authorization uniqueness
```

Final Gate 明确验证了这一边界。

------

# 十、为什么还必须接 WP1 的 Fencing

假设：

```text
A 等待审批
token = 7
```

A 卡住。

然后：

```text
B takeover
token = 8
```

这时用户 APPROVE。

如果 Approval 只判断：

```text
state == APPROVED
```

A 恢复以后仍然可以继续 Tool。

所以 claim 必须一起验证：

```text
run_id
owner_id
fencing_token
lease still ACTIVE
lease_until > DB now()
```

WP2 的真实实现是在同一个 PostgreSQL transaction 中完成：

```text
Run advisory lock
→ current lease/fence validation
→ approval binding/state validation
→ insert execution claim
```

因此不存在：

```text
先检查 ownership
↓
发生 takeover
↓
再 claim
```

这种 TOCTOU。

------

# 十一、跨实例 APPROVE 是怎么实现的

现在：

```text
worker 在 instance A
```

HTTP APPROVE 可以打到：

```text
instance B
```

B 不需要 A 的 Controller。

链路：

```text
B HTTP handler
→ auth
→ Run ownership/resource validation
→ DurableApprovalService.decide()
→ PostgreSQL APPROVED
```

A 的 waiter：

```text
bounded polling
→ 查询 PostgreSQL
→ 发现 APPROVED
→ 本地 wakeup
→ fencing + claim
→ continuation
```

这次 Gate 实际发现了一个很典型的问题：

原实现虽然 B 成功写 PostgreSQL，但 A 的 waiter 只等本地 event，所以 A 永远不知道 B 批准了。

Sol 在 Gate 中发现这是 Blocking P1，然后让 Luna 修成 waiter 有界查询 durable Authority。

这个案例非常适合面试。

------

# 十二、为什么不强制用 Redis Pub/Sub / Kafka 通知

当然可以优化成：

```text
PostgreSQL decision
→ Redis/Kafka notification
→ wake worker
```

但不能让 notification 成为 Approval truth。

通知可能：

```text
丢失
重复
乱序
```

所以当前 WP2 采用：

```text
PostgreSQL = Authority
bounded polling = correctness
local wakeup = optimization
```

如果未来加入通知，也应该是：

```text
notification
→ faster wakeup
```

而不是：

```text
notification
→ decision truth
```

Final Gate 明确保留了这一限制：durable waiter 使用有界 PostgreSQL polling，本 WP 没有引入 LISTEN/NOTIFY。

------

# 十三、WAITING_APPROVAL Recovery 到底恢复了什么

这里非常容易夸大。

WP2 没有实现：

```text
任意 Agent execution state
→ crash
→ 自动续跑
```

它只实现一个非常明确的恢复边界：

```text
WAITING_APPROVAL
```

以及：

```text
APPROVED_PRE_EXECUTION
```

如果 Controller / Worker 消失：

```text
PENDING
```

仍然存在 PostgreSQL。

新的实例仍然可以：

```text
读取 approval
提交 decision
```

恢复/re-entry 时，如果识别到相同：

```text
run_id + invocation_id
```

就复用 durable canonical approval，而不是生成一个新的内存 Approval。

------

# 十四、为什么 APPROVED_PRE_EXECUTION 是很好的恢复边界

考虑：

```text
用户 APPROVE
↓
DB commit
↓
进程 crash
↓
Tool 还没执行
```

这种情况下：

```text
human decision 已经 durable
external side effect 尚未开始
```

这是相对安全的恢复点。

新的 current owner 可以：

```text
load APPROVED
→ binding validation
→ fencing validation
→ execution claim
→ Tool execution
```

WP2 已使用真实 PostgreSQL证明这个路径。

------

# 十五、为什么 Claim 后 Crash 就复杂很多

考虑：

```text
execution claim commit
↓
准备发 HTTP Tool request
↓
process crash
```

有两种情况：

### 情况 A

能证明：

```text
external side effect 尚未开始
```

那么可以安全恢复。

### 情况 B

不能证明：

```text
Provider 到底有没有收到请求
```

这时不能直接重试。

否则可能：

```text
第一次其实已经成功
+
第二次重新执行
=
重复副作用
```

因此 WP2 到这里明确停下。

后续 WP5 解决：

```text
UNKNOWN
provider_operation_id
idempotency
reconciliation
```

Final Gate 将这项保留为 ACCEPTED_P1，而不是假装 WP2 已经支持 exactly-once。

------

# 十六、Approval Invalidation 为什么必要

假设：

```text
Approval=PENDING
```

期间 Run：

```text
被取消
超时
已经 terminal
```

如果 Approval 还保持 PENDING：

几分钟后管理员又点 APPROVE：

系统可能重新执行一个已经失效的 Tool。

所以需要：

```text
PENDING
→ INVALIDATED
```

原因包括：

```text
CANCELLED
DEADLINE_EXCEEDED
RUN_TERMINAL
```

之后：

```text
later APPROVE
```

不能重新激活。

Final Gate 已验证三种 invalidation，并确认 invalidated approval 后续不能重新执行。

------

# 十七、为什么 Approval 不自己拥有 Cancel Truth

Cancel 已经是 WP1 Run Control 的 Authority。

错误设计：

```text
RunControl:
cancelled=true

Approval:
cancelled=true
```

然后两边都能独立决定 Run 是否取消。

这会再次产生双 Authority。

正确设计：

```text
Run Control
= cancellation authority

Approval
= consume cancellation fact
→ INVALIDATED(CANCELLED)
```

Approval 只保存：

> 这份审批为什么不再有效。

它不重新定义：

> Run 是否已经取消。

------

# 十八、认证为什么属于真实 HITL 主链的一部分

WP2 不是只测：

```text
service.decide()
```

Final Gate 还走了真实 FastAPI middleware：

```text
EdDSA Bearer JWT
+
PostgreSQL principal
+
Run ownership
+
HTTP approve
```

然后才进入 DurableApprovalService。

测试还模拟：

```text
HTTP decision instance B
worker instance A
```

最终 APPROVE 产生：

```text
1 durable claim
1 TOOL_STARTED
1 provider committed operation
```

而 REJECT 三者都是 0。

这使 WP2 从：

```text
domain implementation
```

升级成：

```text
production-reachable HITL
```

------

# 十九、工程方法类问答

## Q1：为什么 Approval 要持久化？

因为 Approval 通常跨越多个 HTTP 请求甚至较长时间，不能假设创建 Approval 和用户 Decision 一定落在同一个进程生命周期内。

------

## Q2：为什么不能把 Approval 存 Redis？

技术上可以，但当前 Run control、Journal、identity 和 transaction consistency 都围绕 PostgreSQL。

Approval decision、Run fencing 和 execution claim 又需要强事务边界。

因此 PostgreSQL 更自然。

------

## Q3：为什么 Approval Decision 和 Execution Claim 分离？

因为：

```text
APPROVED
```

是人的授权事实。

而：

```text
execution claim
```

是 Runtime 的执行资格。

一个 Approval 可以已经被批准，但当前 Executor 已经失去 ownership，因此不能执行。

------

## Q4：为什么还要 Fencing？Approval 已经 APPROVED 了啊。

APPROVED 只说明：

> 这个 Invocation 获得人类授权。

不说明：

> 当前这个 Executor 仍然有 Run execution ownership。

所以 continuation 还必须重新验证 WP1 fencing。

------

## Q5：为什么 Approval Binding 不能只用 approval_id？

因为 Approval 需要证明：

> 执行的 Invocation 与人类看到并批准的是同一个。

所以必须绑定 Tool identity、arguments digest、resource、risk 等 immutable facts。

------

## Q6：First-Wins 怎么实现？

使用 PostgreSQL transaction + row lock。

只有 `PENDING` 可以转换到 APPROVED/REJECTED。

第一个提交成功以后，第二个不同 direction 的 decision fail closed。

------

## Q7：重复 APPROVE 怎么处理？

同向重复属于幂等 retry。

返回已有 effective result，不重新创建状态转换，也不会生成第二 execution claim。

------

## Q8：为什么 Controller 还在？

Controller 仍然适合作为 Runtime facade 和本地 waiter。

只是它不再拥有 distributed truth。

------

## Q9：跨实例审批怎么通知原 worker？

目前 correctness 依赖 PostgreSQL bounded polling。

Local event/wakeup 只是优化。

未来可引入 LISTEN/NOTIFY 或 Redis notification 降低 latency，但不能取代 PostgreSQL Authority。

------

## Q10：现在进程挂了以后能完整恢复 Agent 吗？

不能。

只支持：

```text
WAITING_APPROVAL
APPROVED_PRE_EXECUTION
```

两个冻结恢复边界。

任意 planning/model/parallel graph resume 没有实现。

------

## Q11：现在能保证 Tool exactly-once 吗？

不能。

WP2 保证的是：

```text
one durable execution claim
```

不是：

```text
external side effect exactly-once
```

外部系统副作用需要 WP5 的 Idempotency + Reconciliation。

------

# 二十、30 秒面试总结

我们原来的 HITL 审批主要保存在进程内的 ToolApprovalController，所以多实例或者进程重启后，pending approval 和 waiter 都可能丢失。我后来把 Approval Authority 迁移到了 PostgreSQL，APPROVE/REJECT 用事务和行锁保证 first-wins，同向重复 decision 保持幂等。Approval 还绑定完整 Tool Invocation digest，避免出现批准的是一个参数、执行的却是另一个参数。

审批通过以后也不会直接执行 Tool，而是先结合上一阶段的 Run Fencing Token，在同一个数据库事务里校验当前 Run Owner，再获得一个唯一 durable execution claim。这样旧 executor 即使恢复，也拿不到执行资格。现在 HTTP decision 可以打到任意实例，WAITING_APPROVAL 和 APPROVED_PRE_EXECUTION 也可以跨进程恢复。

------

# 二十一、2 分钟面试总结

我在 Agent Runtime 的 HITL 上主要解决了三个问题：durability、cross-instance decision 和 safe continuation。

最初 Approval 是 run-scoped ToolApprovalController 里的内存状态，这在单实例可以工作，但多实例后 HTTP approve 可能落到另一个实例，而且原 worker crash 后 pending approval 也会消失。

所以我把 Approval Authority 迁到了 PostgreSQL。Tool Governance 返回 APPROVAL_REQUIRED 后，会先持久化 PENDING，再进入 WAITING_APPROVAL。APPROVE 和 REJECT 通过数据库事务和 row lock 做 first-wins，同方向 retry 是幂等的，反方向 decision 会 fail closed。

安全上我们没有只绑定 approval_id，而是把 run、step、invocation、tool、arguments、resource、risk 等做 canonical digest。Decision、recovery 和 execution claim 都必须匹配这份 binding。

另外一个关键设计是把 Human Approval 和 Tool Execution Claim 分开。APPROVED 只说明人批准了，不代表当前 executor 可以执行。真正执行前还要结合上一阶段的 Run Lease/Fencing Token，在同一个 PostgreSQL transaction 里验证当前 ownership，然后创建唯一 durable execution claim。这样 stale executor 即使醒过来，也不能执行 Tool。

现在 approval 可以跨实例提交，worker 通过 durable authority 观察 decision；WAITING_APPROVAL 和 APPROVED_PRE_EXECUTION 可以跨进程恢复。不过 claim 以后如果外部 side effect 是否已经发生不确定，我们不会盲重试，这部分留给后续的 idempotency 和 reconciliation。

------

# 二十二、高频追问

## 1. 为什么不用消息队列把 Approval 发给 worker？

MQ 可以做通知，但不能简单作为 Approval Authority。

Approval 需要：

```text
first-wins
binding validation
execution claim
Run fencing
```

这些都和 PostgreSQL transactional state 强相关。

MQ 可以未来加速 wakeup，但 durable truth 仍在 PostgreSQL。

------

## 2. 如果 APPROVE 和 CANCEL 同时发生怎么办？

Approval 是否被批准是一件事。

Run 是否仍具有合法 execution ownership 是另一件事。

即使 APPROVED，后续 execution claim 仍必须验证 current Run control/fence。

所以 CANCEL / terminal / ownership loss 后，不会因为旧 APPROVED 状态绕过 Runtime safety。

------

## 3. 如果两个实例同时获得 APPROVED，都会执行吗？

不会。

APPROVED 是共享 durable truth，但执行资格由独立 durable execution claim 控制。

`approval_id` 唯一约束保证只产生一个合法 claim。

------

## 4. 如果旧 worker一直等本地 event 怎么办？

这正是 Final Gate 实际发现的问题。

原实现跨实例 decision 成功写 PostgreSQL后，worker 只等 local event，所以永远醒不过来。

修复后 waiter 会有界查询 DurableApprovalService。

------

## 5. PostgreSQL 挂了怎么办？

Fail closed。

不能因为本地 Controller 还显示 APPROVED 就继续执行。

如果无法证明当前 approval / fencing / claim 状态，就不能获得新的执行资格。

------

# 二十三、Bad Case

## Bad Case 1：Approval 只存在内存

```text
A waits approval
A crash
→ approval lost
```

完全不具备 durable HITL。

------

## Bad Case 2：HTTP Approval 找本地 Controller

```text
A executes
B receives APPROVE

B registry/controller miss
→ 404
```

多实例直接失败。

------

## Bad Case 3：APPROVED 后直接执行

```text
if approval.state == APPROVED:
    tool.execute()
```

没有 Run fencing，也没有 execution claim。

stale executor 或多个 worker 都可能执行。

------

## Bad Case 4：只用 approval_id 做 Binding

人批准 A Invocation，恢复后当前 Invocation 已经改变，但系统仍执行。

属于典型 confused deputy / approval replay 风险。

------

## Bad Case 5：APPROVE 与 REJECT Last-Write-Wins

```text
APPROVE
↓
REJECT
↓
APPROVE
```

审批事实可以随意反转。

正确的是 PENDING first transition wins。

------

## Bad Case 6：Decision 写 PostgreSQL，但 Worker 只等 Local Event

数据库里：

```text
APPROVED
```

Worker：

```text
still waiting forever
```

这就是 Final Gate 真实发现并修复的问题。

------

## Bad Case 7：把 Approval 和 Tool Execution 合成一个状态机

```text
APPROVED
EXECUTING
COMPLETED
```

全部塞 approval table。

结果 Approval Authority 开始侵入 Tool Execution Authority，形成职责混乱。

------

## Bad Case 8：Claim 后 Crash 直接重试 Tool

第一次调用可能已经成功，只是 response 丢失。

直接 retry：

```text
副作用重复
```

正确做法是进入后续 WP5 的 UNKNOWN / reconciliation。

------

# 二十四、本 WP 最需要记住的三个知识点

## 第一：Approval Truth 和 Waiter 必须分离

```text
PostgreSQL
= approval truth

Controller
= local waiter/facade
```

------

## 第二：APPROVED != EXECUTABLE

真正执行需要：

```text
APPROVED
+
Binding Match
+
Current Run Fencing
+
Unique Execution Claim
```

------

## 第三：恢复边界必须诚实

WP2 不是：

```text
full Agent crash recovery
```

而是：

```text
WAITING_APPROVAL
+
APPROVED_PRE_EXECUTION
```

这两个明确、可验证的恢复点。

------

# 二十五、Truth / Completion Boundary

## 已真实完成

### PostgreSQL Durable Approval

Approval canonical state 已迁移 PostgreSQL。

### Cross-instance APPROVE / REJECT

HTTP decision 可以命中与 worker 不同的实例。

### First-Wins

APPROVE vs REJECT 并发只有一个有效 decision。

### Decision Idempotency

同向重复 decision 返回已有有效结果。

### Binding Validation

Decision 和 Execution Claim 都验证 immutable invocation binding。

### Run Fencing on Continuation

stale executor 无法继续获得 execution claim。

### Durable Execution Claim

Approval Decision 与执行资格独立持久化。

### Single Execution Claim

同一个 Approval 只能获得一个 durable pre-execution claim。

### WAITING_APPROVAL Recovery

process-local waiter/controller 消失后，durable approval 仍然存在并可继续。

### APPROVED_PRE_EXECUTION Recovery

批准之后、Tool 尚未执行时，可以由新的 current owner 恢复 continuation。

### Approval Invalidation

支持：

```text
CANCELLED
DEADLINE_EXCEEDED
RUN_TERMINAL
```

### Production Reachability

Final Gate 使用真实 production components、真实 PostgreSQL、FastAPI auth、EdDSA JWT、Run ownership 和 Tool continuation 验证完整链路。

------

# 二十六、尚未完成

## 任意 Agent Crash Resume

未实现。

## Planning / Parallel Graph Resume

未实现。

## Model Stream Resume

未实现。

## External Tool Exactly-once

未实现。

## UNKNOWN / Reconciliation

未实现，属于 WP5。

## Provider Operation Correlation

未实现，属于 WP5。

## LISTEN/NOTIFY / Redis Approval Notification

未实现，也不是 correctness 必需。

------

# 二十七、面试不能夸大的地方

不要说：

> “我们实现了完整 Agent Crash Recovery。”

应该说：

> “我们实现了 Approval Boundary 的持久化恢复，目前支持 WAITING_APPROVAL 和 APPROVED_PRE_EXECUTION。”

不要说：

> “APPROVE 后 Tool exactly-once。”

应该说：

> “APPROVE 后只有一个合法 executor 能获得 durable execution claim，但 external side-effect exactly-once 还需要 provider idempotency 和 reconciliation。”

不要说：

> “ToolApprovalController 是审批状态机。”

应该说：

> “Controller 是 Runtime facade/waiter，PostgreSQL DurableApprovalService 才是 Approval Authority。”

------

# 二十八、一句话总结

> WP2 的本质不是“把审批状态存数据库”，而是把 HITL 从进程内交互升级成 **Durable Approval + Immutable Binding + First-Wins Decision + Run Fencing + Unique Execution Claim + Bounded Recovery** 的安全执行协议。