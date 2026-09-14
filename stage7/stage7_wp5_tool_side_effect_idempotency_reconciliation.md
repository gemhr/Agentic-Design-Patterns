# Stage7-WP5 — Tool Side-effect Idempotency & Reconciliation

## 一、本 WP 到底解决了什么问题

WP5 解决的是 Agent Tool Runtime 里最危险的一类问题：

> **外部副作用可能已经发生了，但 LocalAgent 没拿到可信结果，此时到底该不该重试？**

例如：

```text
Runtime
→ 调用外部 Tool
→ 外部系统已经完成操作
→ Response 丢失 / Timeout / Process Crash
```

此时本地无法确定：

```text
到底成功了？
还是根本没执行？
```

如果直接：

```text
Timeout
→ FAILED
→ Retry
```

就可能把副作用执行两次。

WP5 最终采用的不是：

```text
generic external exactly-once
```

而是：

```text
durable idempotency intent
+
single active fenced executor
+
explicit UNKNOWN
+
provider-specific reconciliation
```

这是本 WP 最核心的一句话。

------

# 二、最终生产链路

当前真实链路是：

```text
server.py::lifespan()
→ ToolRegistry / AgentRouter
→ ToolGovernanceService
→ WP2 Approval + Durable Execution Claim
→ ToolExecutionService
→ DurableToolInvocationService.prepare()
→ WP1 Run Lease / Fencing validation
→ DurableToolInvocationService.start()
→ ToolAdapter Provider Boundary
→ COMMITTED / UNKNOWN
→ Provider-specific Reconciliation
→ DurableToolInvocationService.reconcile()
```

其中：

```text
WP1
负责谁现在有执行资格

WP2
负责是否获得人工授权和执行 Claim

WP5
负责外部副作用到底处于什么状态
```

三者职责没有混在一起。

------

# 三、名词 / 概念速览

### 幂等意图（Idempotency Intent）

在执行外部副作用前，先为这次逻辑操作确定一个稳定身份，让重复进入仍然代表同一次操作。

### 副作用（Side Effect）

会修改外部世界状态的操作，例如创建、写入、发送、扣款、提交订单等。

### 持久化调用聚合（Durable Tool Invocation Aggregate）

PostgreSQL 中保存 Tool 副作用执行状态的权威记录。

### PREPARED

调用意图已经可靠持久化，但还没有跨过外部副作用可能发生的边界。

### STARTED

LocalAgent 已进入外部副作用不确定区间；从这一步开始，不能再轻易假设“肯定没执行”。

### COMMITTED

有可信证据证明外部副作用已经成功完成。

### UNKNOWN

LocalAgent 既不能证明操作成功，也不能证明没有发生。

### NOT_COMMITTED

通过 Provider Reconciliation 明确证明外部操作没有提交。

### 对账 / 调和（Reconciliation）

通过外部 Provider 提供的 operation ID、idempotency key 或 status API，查询这次副作用最终到底发生了什么。

### Fencing Token

WP1 中用于阻止旧 Executor 在失去 Lease 后继续修改共享状态的递增令牌。

### CAS（Compare-and-Swap）

只允许在当前状态 / version 仍符合预期时进行状态更新，防止并发覆盖。

### Provider Operation Correlation

把 LocalAgent Invocation 和 Provider 侧真实 operation 关联起来的稳定身份，如 `provider_operation_id`。

### Fail Closed

状态不确定时拒绝继续执行，而不是猜测成功、失败或盲目重试。

------

# 四、为什么 UNKNOWN 是一等状态

这是 WP5 最重要的设计。

传统代码很容易只有：

```text
SUCCESS
FAILED
```

但外部副作用不是这么简单。

例如：

```text
POST /create-order
→ Provider 已经创建订单
→ Response 在网络中丢失
```

LocalAgent 只看到：

```text
Timeout
```

但是：

```text
Timeout
≠
Provider 没执行
```

所以不能：

```text
Timeout → FAILED
```

必须：

```text
Timeout after external boundary
→ UNKNOWN
```

WP5 明确保证：

```text
UNKNOWN != FAILED
UNKNOWN != NOT_COMMITTED
```

包括 Timeout、Connection Drop、Cancel、Deadline、Malformed Response、Provider 已成功但本地 COMMITTED 持久化失败等，只要外部副作用已经可能发生，都进入 `UNKNOWN`。

------

# 五、为什么 UNKNOWN 不能自动 Retry

假设：

```text
第一次请求：
Provider 实际成功
Response 丢失
Local = UNKNOWN
```

如果 Runtime 自动：

```text
retry_count < 3
→ Retry
```

第二次可能又执行一次副作用。

因此 WP5 的规则是：

```text
UNKNOWN
→ 禁止 Generic Retry
```

只有 Reconciliation 明确证明：

```text
NOT_COMMITTED
```

以后，才可能由具体 Tool Policy 决定是否重新执行。

而：

```text
reconcile()
```

本身也不会偷偷重新执行 Provider Side Effect。

------

# 六、PREPARED 为什么重要

`PREPARED` 表示：

> ToolInvocation 的不可变执行意图已经写入 PostgreSQL，但还没有进入外部副作用区域。

它保存的核心内容包括：

```text
run
step
invocation
canonical tool
binding digest
idempotency digest
resource digest
approval / claim linkage
```

而且不会保存：

```text
raw arguments
secret
credential
```

相同 immutable invocation replay 会返回 canonical durable record，而不是新建一次新的逻辑操作。

------

# 七、STARTED 为什么必须先于 Provider Call 持久化

正确顺序：

```text
PREPARED
↓
STARTED
↓
COMMIT DB transaction
↓
调用 Provider
```

不能：

```text
调用 Provider
↓
Provider 可能已经执行
↓
再写 STARTED
```

原因很简单。

如果 Provider 已经执行之后：

```text
process crash
```

但本地数据库还停留在：

```text
PREPARED
```

恢复节点就可能认为：

> 外部操作还没开始，可以重新执行。

这会造成重复副作用。

WP5 Final Gate 已确认生产链在调用 Provider 前持久化 `STARTED`。

------

# 八、状态机怎么理解

WP5 的核心状态机：

```text
PREPARED
    ↓
STARTED
   ├────────→ COMMITTED
   │
   └────────→ UNKNOWN
                  ├──→ COMMITTED
                  └──→ NOT_COMMITTED
```

如果 Provider Reconciliation 返回：

```text
STILL_PENDING
UNKNOWN
```

本地继续保持：

```text
UNKNOWN
```

不会强行收口。

同时：

```text
PREPARED
```

不能直接进入 UNKNOWN，因为 PREPARED 还没跨过 External Boundary。

也不存在：

```text
STARTED → FAILED → Retry
```

这样的通用路径。

------

# 九、为什么 STARTED 只能发生一次

Final Gate 实际发现过一个严重问题：

```text
STARTED / UNKNOWN / terminal record
还能再次 start()
```

这样可能导致：

```text
same logical invocation
→ provider called again
```

最终修复为：

```text
start()
只允许 PREPARED → STARTED
```

重复进入不会重新拿到 Provider execution 权。

------

# 十、Stable Idempotency Identity 是什么

同一逻辑操作必须拥有稳定的 Idempotency Identity。

当前优先使用：

```text
ToolInvocation.idempotency_key
```

没有时使用被冻结的 invocation identity。

数据库保存的是：

```text
SHA-256 digest
```

而不是原始敏感内容。

此外还增加：

```text
(run_id, tool_name, idempotency_key_digest)
```

唯一约束。

因此不能通过：

```text
同一个操作
→ 换一个新的 invocation UUID
```

绕过 durable ledger 再执行一次。

------

# 十一、Idempotency 和 Exactly-once 有什么区别

这是面试高频坑。

Idempotency 的目标是：

> 重复请求尽量映射到同一个逻辑操作。

但它并不自动保证：

```text
外部系统绝对只执行一次
```

例如第三方系统根本不支持：

```text
idempotency key
status query
operation ID
```

LocalAgent 无法凭空创造 Exactly-once。

所以 WP5 明确不宣称：

```text
generic external exactly-once
```

而只承诺：

```text
durable intent
single active fenced executor
explicit UNKNOWN
provider-specific reconciliation
```

Final Gate 还专门审计了全仓 Exactly-once 文案，并保留 system/end-to-end exactly-once 为 `NOT_IMPLEMENTED`。

------

# 十二、Fencing 在 WP5 中解决什么

Idempotency 并不能阻止两个进程同时执行。

例如：

```text
Instance A
fencing token = 10

Lease expires

Instance B takeover
fencing token = 11
```

如果 A 网络卡顿后恢复，又继续执行 Tool，就可能出现双执行。

所以 WP5 所有权威 mutation 都校验：

```text
run_id
owner_id
fencing_token
status = ACTIVE
lease_until > database now()
```

旧 A/token=10 在 B/token=11 takeover 后，不能：

```text
START
COMMIT
mark UNKNOWN
reconcile
```

真实 PostgreSQL 测试已经验证。

------

# 十三、为什么 Fencing 和 Idempotency 两者都需要

两者解决的问题不同。

### Idempotency

解决：

```text
同一个逻辑操作
被重复请求
```

### Fencing

解决：

```text
旧 Executor 已经失去 ownership
但仍试图继续写
```

所以：

```text
Idempotency
≠
Distributed Ownership
```

真正安全需要：

```text
Stable Idempotency Identity
+
Current Fencing Token
```

------

# 十四、WP2 Execution Claim 和 WP5 STARTED 有什么区别

WP2：

```text
APPROVED
+
Execution Claim
```

解决：

> 这次 Tool 有没有资格开始执行？

WP5：

```text
PREPARED
STARTED
COMMITTED / UNKNOWN
```

解决：

> 获得资格以后，外部副作用实际发生到什么程度？

所以：

```text
Execution Claim
≠
Side-effect Outcome
```

WP5 没有让：

```text
runtime_tool_approvals
runtime_tool_execution_claims
```

承担 Provider Outcome Truth。

------

# 十五、为什么 Provider Adapter 不能直接改数据库

Provider Adapter 的职责只是：

```text
调用 Provider
查询 Provider
把 Provider 状态规范化
```

例如返回：

```text
COMMITTED
NOT_COMMITTED
STILL_PENDING
UNKNOWN
```

但它不能：

```text
UPDATE runtime_tool_invocations
```

因为 LocalAgent 还需要验证：

```text
Run fencing
binding
CAS/version
current local state
```

所以：

```text
Provider Adapter
→ Query / Normalize

DurableToolInvocationService
→ Local authoritative transition
```

这样 Provider 不会变成 Local Runtime Authority。

------

# 十六、Reconciliation 为什么重要

假设：

```text
Provider committed
↓
response lost
↓
Local = UNKNOWN
```

恢复后不能：

```text
Retry Provider
```

而应该：

```text
provider_operation_id / idempotency key
↓
query provider
↓
COMMITTED
↓
Local UNKNOWN → COMMITTED
```

这样：

```text
provider execution count = 1
```

WP5 已真实验证这个 Crash Window。

------

# 十七、四种 Reconciliation Result

## COMMITTED

Provider 明确证明：

```text
操作已成功
```

Local：

```text
UNKNOWN → COMMITTED
```

------

## NOT_COMMITTED

Provider 明确证明：

```text
操作没发生
```

Local：

```text
UNKNOWN → NOT_COMMITTED
```

但是并不代表：

```text
立即自动 Retry
```

------

## STILL_PENDING

Provider 明确知道这次 operation：

```text
还没结束
```

Local：

```text
继续 UNKNOWN / open
```

------

## UNKNOWN

Provider 自己也无法确认。

Local：

```text
继续 UNKNOWN
```

必要时进入：

```text
operator/manual boundary
```

------

# 十八、Provider 没有 Status API 怎么办

这是非常典型的 Production Reality。

如果 Provider：

```text
没有 operation query
没有 idempotency lookup
没有 transaction status
```

那 LocalAgent 就没有证据判断最终结果。

正确答案：

```text
UNKNOWN remains UNKNOWN
```

进入：

```text
人工 / Operator 处理
```

而不是：

```text
过 30 秒没消息
→ assume FAILED
```

也不能：

```text
再发一次试试看
```

Final Gate 明确把这一点作为允许的 capability boundary。

------

# 十九、为什么 Concurrent Reconciliation 还需要 CAS

两个实例可能同时：

```text
Reconciler A
Reconciler B
```

处理同一个 UNKNOWN。

如果没有 CAS / row lock：

```text
A → COMMITTED
B → NOT_COMMITTED
```

可能互相覆盖。

WP5 使用：

```text
row lock
fencing
version increment
CAS
```

确保只有一个 effective transition。

另一个 Reconciler 最终读取 canonical terminal state。

并发测试使用真实 PostgreSQL 已验证。

------

# 二十、Crash Window 为什么是本 WP 的重点

## Window 1

```text
PREPARED
→ Crash
```

因为还没有跨 external boundary：

```text
新的 current owner
可以继续 START
```

------

## Window 2

```text
STARTED
→ Crash
```

不能：

```text
重新执行
```

必须：

```text
UNKNOWN-safe recovery
→ Reconcile first
```

------

## Window 3

```text
Provider committed
→ Response lost
```

Local：

```text
UNKNOWN
```

通过 Reconciliation 确认 COMMITTED。

------

## Window 4

```text
Provider success response
→ Local COMMITTED persistence 前 crash
```

Local 还是：

```text
STARTED / UNKNOWN
```

恢复后：

```text
Query Provider
```

而不是：

```text
再次执行
```

四个窗口都已经进入 Final Gate 证据。

------

# 二十一、Cancellation 为什么不能等同于 Tool Cancelled

假设：

```text
Tool request
已经发到 Provider
```

此时用户：

```text
Cancel Run
```

Local Runtime 可以停止等待。

但 Provider 可能已经：

```text
创建订单
发送消息
修改资源
```

所以：

```text
Run CANCELLED
```

只能说明：

> Local Run 生命周期终止了。

不能说明：

```text
External Tool NOT_COMMITTED
```

只要副作用可能已经发生：

```text
Tool Outcome = UNKNOWN
```

WP5 明确分离 Run Truth 和 Provider Operation Truth。

------

# 二十二、Timeout 也一样

Timeout 的含义只是：

> 我没有在规定时间内获得可信结果。

不代表：

> 外部操作没有发生。

所以：

```text
Provider Timeout
```

如果已经跨 External Boundary：

```text
→ UNKNOWN
```

而不是：

```text
→ FAILED
```

这一句话面试里非常重要：

> **Timeout 是“我没拿到答案”，不是“操作失败了”。**

------

# 二十三、Representative Provider 为什么只做一个

WP5 没有尝试：

```text
把所有 Tool Provider
全部做成统一 Reconciliation Framework
```

而只选择：

```text
complex_workflow_simulator
```

作为 Representative Side-effect Tool。

它能模拟：

```text
commit + success
commit + response lost
NOT_COMMITTED
STILL_PENDING
UNKNOWN
```

并支持稳定的 Provider Operation Correlation。

这么做的目的：

> 先证明 Runtime Protocol 正确，而不是为了一个 WP 搭建 Universal Integration Platform。

------

# 二十四、为什么不用“最近一条 Provider 记录”做 Reconciliation

错误方案：

```text
找这个 resource 最近一条 operation
→ 猜它就是当前 invocation
```

并发情况下非常危险。

正确方式：

```text
provider_operation_id
```

或者：

```text
stable idempotency identity
```

精确定位。

WP5 明确禁止：

```text
latest-operation
latest-resource
模糊猜测
```

------

# 二十五、Legacy 兼容策略

本 WP 还落实了一个重要长期规则：

> Legacy / Deprecated / Obsolete 链路不再自动获得 Compatibility Requirement。

Final Gate 审计确认：

```ini
LEGACY_COMPATIBILITY_REQUIRED = NO
COMPATIBILITY_REQUIRED = NO
```

Canonical Durable Run 的 side-effect Tool：

```text
如果没有 DurableToolInvocationService
→ Provider Boundary 前 fail closed
```

不会为了旧 non-durable construction path 继续偷偷执行。

旧 constructor 只保留：

```text
no-durable-lease unit / legacy seam
```

而不是 production bypass。

------

# 二十六、工程方法类问答

## Q1：为什么 Tool Side Effect 不能简单做数据库事务？

因为：

```text
Local PostgreSQL
```

和：

```text
第三方 Provider
```

通常不在一个数据库事务里。

你没法用：

```text
BEGIN
external HTTP
COMMIT
```

获得真正跨系统原子性。

------

## Q2：为什么不用 2PC？

多数 SaaS / Tool Provider 根本不支持两阶段提交（Two-Phase Commit, 2PC）。

而且成本、复杂度和耦合都太高。

WP5 不走 Distributed Transaction 路线。

------

## Q3：那为什么不直接 Exactly-once？

Exactly-once 需要 Provider 自己提供非常强的幂等和事务语义。

LocalAgent 单方面无法保证。

所以只承诺：

```text
at-most-one active legitimate executor
+
idempotency intent
+
uncertainty handling
```

------

## Q4：Idempotency Key 已经有了，为什么还需要 UNKNOWN？

因为 Provider 即使支持幂等，你仍可能不知道第一次请求是否已经成功。

Idempotency 降低重复执行风险，但不自动告诉你当前 operation 的最终状态。

------

## Q5：为什么 UNKNOWN 不直接长期保持，非要 Reconciliation？

可以长期保持，但如果 Provider 提供可靠 status API，就应该主动查询，把 uncertainty 收敛。

------

## Q6：Reconciliation 为什么不能自己 Retry？

因为 Reconciliation 的职责是：

```text
确认事实
```

不是：

```text
制造新的副作用
```

否则 Query 和 Execute 权限混在一起。

------

## Q7：为什么 Approval Claim 还不够？

Approval Claim 只能证明：

```text
“你现在可以执行”
```

不能证明：

```text
“Provider 最终执行成功了”
```

------

## Q8：为什么 Fencing 还要检查 Reconciliation？

因为旧实例即使不能重新执行，也不能在失去 ownership 后拿一个 Provider 查询结果回来覆盖新 Owner 的状态。

------

## Q9：为什么 `PREPARED → UNKNOWN` 不允许？

因为 PREPARED 定义上还没跨外部副作用边界。

如果还没开始外部执行，本地不能说“外部结果未知”。

------

## Q10：为什么 `NOT_COMMITTED` 也不能自动重试？

因为“Provider 没执行”只是重试的必要条件之一。

还需要具体 Tool Policy 判断：

```text
现在是否仍然应该执行？
业务是否已取消？
资源状态是否改变？
```

------

# 二十七、30 秒面试总结

我们对有外部副作用的 Tool 没有宣称 generic exactly-once，因为跨第三方系统通常做不到。我们采用的是 durable idempotency intent、Run fencing、UNKNOWN 和 provider-specific reconciliation。

执行前先把 invocation 写成 PREPARED，再在调用 Provider 前持久化 STARTED。只要请求可能已经到 Provider，但本地拿不到可信结果，比如 Timeout、断线或者进程崩溃，就进入 UNKNOWN，禁止普通 Retry。

如果 Provider 支持 operation status query，我们用 operation ID 或稳定 idempotency identity 做 reconciliation，把 UNKNOWN 收口成 COMMITTED、NOT_COMMITTED，或者继续保持 UNKNOWN。整个本地状态转换还会检查 Run fencing 和 PostgreSQL CAS，防止旧 Executor 或并发 Reconciler 覆盖状态。

------

# 二十八、2 分钟面试总结

Tool Runtime 里我比较关注的一类问题是外部副作用的不确定性。

比如 Agent 调第三方系统创建一个资源，Provider 实际已经成功，但 Response 丢了。本地看到 Timeout，如果简单标记 FAILED 然后 Retry，就有可能重复创建。

所以我们没有声称 external exactly-once，而是给 side-effect Tool 建了一个 PostgreSQL durable invocation aggregate。状态先是 PREPARED，表示 immutable invocation intent 已经持久化；在真正调用 Provider 前先提交 STARTED，从这个时刻开始认为已经跨过 external uncertainty boundary。

正常成功会进入 COMMITTED。如果 Timeout、Connection Drop、Cancel、进程 Crash 或 Provider 成功但本地持久化失败，只要不能证明外部操作没发生，就进入 UNKNOWN。UNKNOWN 不允许 generic Retry。

之后如果 Provider 支持查询，就通过 provider operation ID 或 stable idempotency key 做 reconciliation，Provider Adapter 只负责查询和规范化为 COMMITTED、NOT_COMMITTED、STILL_PENDING 或 UNKNOWN，本地 DurableToolInvocationService 再结合 Fencing、CAS 和 Binding 做权威状态转换。

这套链路同时接了我们前面做的 Run Fencing 和 HITL Execution Claim。Approval 只证明有资格执行，WP5 才负责外部 Side Effect 的最终 Truth。对于没有 status API 的 Provider，我们宁愿一直保持 UNKNOWN 并转人工，也不会猜测失败然后盲重试。

------

# 二十九、高频追问

## 1. 你们是不是 Exactly-once？

不是。

准确说法是：

```text
durable idempotency intent
+
single active fenced executor
+
UNKNOWN
+
provider-specific reconciliation
```

------

## 2. Idempotency 和 Exactly-once 差在哪？

Idempotency 可以让重复请求映射到同一逻辑操作，但 Exactly-once 还要求整个跨系统执行最终只发生一次并且结果可确定。

后者需要 Provider 合作。

------

## 3. Provider Timeout 后怎么办？

如果请求可能已经发出：

```text
UNKNOWN
```

不能普通 Retry。

------

## 4. 如果 Provider 没有查询 API 呢？

保持 UNKNOWN。

进入人工/operator boundary。

------

## 5. Provider 已经返回成功，但写本地 DB 时挂了呢？

恢复时仍然不能 Retry Provider。

使用相同 operation correlation 查询 Provider，再把本地收口为 COMMITTED。

------

## 6. 为什么不做补偿事务？

当前 WP 没实现 Compensation/Saga。

并且很多外部副作用本来就无法可靠补偿。

------

## 7. 多实例同时 Reconcile 怎么办？

PostgreSQL row lock + current fencing + CAS/version，保证一个 effective transition。

------

## 8. 新 Owner Takeover 后能直接重新执行 STARTED Tool 吗？

不能。

`STARTED` 表示已经进入 External Uncertainty Boundary，Takeover 必须先 reconciliation。

------

# 三十、Bad Case

## Bad Case 1：Timeout → FAILED → Retry

第一次操作可能已经成功。

会制造重复副作用。

------

## Bad Case 2：Provider 调用后才写 STARTED

Crash Window 中可能出现：

```text
Provider 已执行
Local 仍 PREPARED
```

恢复节点会误重试。

------

## Bad Case 3：只靠 Idempotency Key，不做 Fencing

两个 Executor 仍可能同时向 Provider 发请求。

------

## Bad Case 4：只做 Fencing，不做 Idempotency

同一业务操作可以用新的 invocation identity 再次进入。

------

## Bad Case 5：Reconcile 查询最近一条 Operation

并发情况下可能把其他请求的结果认成当前 Invocation。

------

## Bad Case 6：Provider Adapter 直接更新 Local DB

Provider Adapter 会越权成为 Local State Authority。

------

## Bad Case 7：Run Cancel → Tool NOT_COMMITTED

Run 生命周期和 External Operation Truth 是两回事。

------

## Bad Case 8：STARTED Crash 后 Blind Replay

最典型的重复副作用来源之一。

------

## Bad Case 9：为了兼容 Legacy non-durable path，让 Durable Run 缺 Service 时继续执行

会绕过 WP5 的整个安全闭环。

Final Gate 已改成 Provider Boundary 前 fail closed。

------

# 三十一、本 WP 最重要的三个知识点

## 第一：Timeout 不是 Failure Truth

```text
Timeout
=
我不知道结果
```

不是：

```text
操作没发生
```

------

## 第二：UNKNOWN 必须是状态机中的一等公民

不能把所有异常都压成：

```text
FAILED
```

否则 Runtime 会做出错误 Retry 决策。

------

## 第三：Exactly-once 不是 Runtime 单方面能制造出来的

真正能做的是：

```text
Fencing
Idempotency
Durable State
Reconciliation
Fail Closed
```

------

# 三十二、Truth / Completion Boundary

## 已真实完成

### Durable Tool Invocation Aggregate

PostgreSQL 是唯一 durable side-effect coordination authority。

### PREPARED

Immutable Invocation Intent 可持久恢复。

### STARTED

Provider Boundary 前先持久化。

### COMMITTED

有权威成功证据后关闭。

### UNKNOWN

外部结果不确定时保留。

### NOT_COMMITTED

只由 Provider Reconciliation 明确证明。

### Stable Idempotency Identity

同一逻辑 operation 不能靠新 invocation UUID 绕过。

### Run Fencing

Stale Executor 无权 START / COMMIT / UNKNOWN / Reconcile。

### Approval / Claim Integration

WP2 只拥有执行授权，WP5 独立拥有 Side-effect Outcome。

### Provider Correlation

使用明确 operation ID / stable identity。

### Reconciliation

支持：

```text
COMMITTED
NOT_COMMITTED
STILL_PENDING
UNKNOWN
```

### Concurrent Reconciliation

真实 PostgreSQL CAS / row lock / fencing 验证。

### Crash Recovery

STARTED crash 不 blind replay。

### Timeout / Connection Drop

跨 External Boundary 后进入 UNKNOWN。

### Production Reachability

`complex_workflow_simulator` 走真实生产 Tool Runtime。

### Real PostgreSQL

migration、Fencing、CAS、并发、Crash Window 均已有真实 DB Evidence。

### Legacy Canonical Bypass

已破坏性关闭。

Durable Run 缺 WP5 service：

```text
fail closed
```

而不是继续 non-durable execute。

------

# 三十三、尚未完成

## Generic External Exactly-once

未实现，也明确禁止这样宣称。

## All Tool Provider Reconciliation

目前只有一个 representative provider。

## Provider Without Status API Automatic Resolution

没有。

只能 UNKNOWN + manual/operator。

## Compensation Engine

未实现。

## Saga

未实现。

## Distributed Transaction / 2PC

未实现。

## Universal Tool Reconciliation Framework

未实现。

以上均属于当前明确的 capability boundary。

------

# 三十四、面试中不能夸大的地方

不要说：

> “我们的 Tool 可以保证 exactly-once。”

应该说：

> “我们不宣称 generic external exactly-once，而是使用 durable idempotency intent、fencing、UNKNOWN 和 provider-specific reconciliation 控制重复副作用风险。”

不要说：

> “Timeout 后我们知道 Provider 没执行。”

应该说：

> “如果请求可能已经跨过 external boundary，Timeout 只能说明结果未知。”

不要说：

> “任何 UNKNOWN 都可以自动恢复。”

应该说：

> “只有 Provider 能提供可靠 status query 时才能自动 reconciliation，否则需要保持 UNKNOWN 或人工处理。”

不要说：

> “所有 Tool 都已经支持这套 reconciliation。”

应该说：

> “当前使用一个 production-reachable representative side-effect Tool 验证完整 contract。”

------

# 三十五、一句话总结

> WP5 的本质不是实现“Exactly-once Tool”，而是承认跨系统副作用存在不可消除的不确定性，并通过 **Durable Intent + STARTED Boundary + Fencing + UNKNOWN + Reconciliation + No Blind Retry** 把这种不确定性变成可持久化、可审计、可安全恢复的 Runtime 状态。