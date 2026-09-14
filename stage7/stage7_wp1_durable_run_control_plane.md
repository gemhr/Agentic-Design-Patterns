# Stage7-WP1 — Durable Multi-instance Run Control Plane

## 一、本 WP 解决了什么问题

WP1 解决的不是“如何把 Agent 跑起来”，而是：

> 当 LocalAgent 从单实例走向多实例后，如何保证同一个 Agent Run 在同一时刻只有一个合法执行者，并且旧执行者失去执行权后无法继续修改权威状态。

WP1 之前，`RunRegistry` 主要保存当前进程里的 active run handle。

这种设计在单进程里足够，但多实例以后会出现：

```text
instance A
正在执行 run-123

instance B
自己的 RunRegistry 中没有 run-123

B 无法知道：
run-123 到底不存在
还是正在 A 上运行
```

更严重的是：

```text
A 获得执行权
↓
A 卡顿 / 网络抖动
↓
lease 到期
↓
B takeover
↓
A 又恢复
```

如果没有栅栏令牌（Fencing Token），A 和 B 都可能继续认为自己有执行权。

WP1 最终将 Run execution ownership 从 process-local truth 提升成：

```text
PostgreSQL durable control plane
+
single active executor lease
+
monotonic fencing token
```

生产链已经真正接入：

```text
server lifespan
→ DurableRunControlService
→ CoordinatedRuntimeFactory
→ claim Run ownership
→ preflight renew
→ heartbeat renew
→ durable cancel polling
→ RunCoordinator
→ RUN_COMPLETED
→ fence validation
→ terminal Journal append
→ control CLOSED
```

其中最后三步处在同一个 PostgreSQL transaction 中。

------

# 二、名词 / 概念速览

### 持久化运行控制面（Durable Run Control Plane）

把 Run 的 owner、lease、fencing、cancel 等控制事实存进可靠持久化存储，而不是只存在某个 Python 进程的内存里。

### 租约（Lease）

执行者只能在一段有限时间内拥有 Run，需要周期续租才能继续证明自己仍然是合法 Owner。

### 所有者（Owner）

当前被允许执行某个 Run 的应用实例 / executor，不是用户身份。

### 租约续期（Lease Renewal）

当前 Owner 周期性延长 lease，避免正常运行的长任务被其他实例错误 takeover。

### 接管（Takeover）

只有数据库确认旧 lease 已经过期，新实例才能获取 Run ownership。

### 栅栏令牌（Fencing Token）

每次新的 ownership generation 都获得更大的单调递增 token，用于阻止旧执行者恢复后继续进行权威写入。

### 陈旧执行者（Stale Executor）

已经失去 ownership，但因为线程阻塞、网络恢复等原因仍继续运行的旧 executor。

### 数据库时间（Database Time）

Lease 是否过期由 PostgreSQL 的 `now()` 判断，而不是依赖不同机器自己的本地时钟。

### 持久化取消（Durable Cancellation）

取消请求先写进 PostgreSQL，即使请求落到另一个 API 实例，也能最终被真正执行 Run 的实例观察到。

### 快速唤醒（Fast Wakeup）

`RunRegistry` 仍可用于当前进程内快速触发 cancel，但只是一种优化，不再拥有业务真值。

### 终态真值（Terminal Truth）

Run 最终成功、失败、取消等 canonical terminal truth 仍由 Runtime Journal 拥有，而不是 Run control row。

### 原子终态收口（Atomic Terminal Finalization）

fencing 校验、terminal Journal append 和 Run control close 必须在一个事务里一起成功或一起失败。

### 比较并交换（Compare-And-Swap, CAS）

只有当前状态、owner、token 等条件仍符合预期时才允许更新，用于实现并发安全的状态转换。

### 检查后使用竞争（Time-of-Check to Time-of-Use, TOCTOU）

先在一个事务验证 ownership，再在另一个事务进行写入，中间可能发生 takeover，因此验证结果已经失效。

------

# 三、为什么不能继续只用 RunRegistry

最简单的单实例实现是：

```text
RunRegistry = {
    run_id: RunHandle
}
```

优点很明显：

- 快；
- 实现简单；
- cancel 很容易；
- shutdown 时容易遍历 active runs。

但它本质上是：

```text
process-local state
```

instance A 和 instance B 没有共同真值。

因此它不能回答：

```text
run-123 当前是否 active？
谁在执行？
ownership 是否过期？
旧 executor 还能不能继续写？
```

所以 WP1 没有删除 RunRegistry，而是把它重新定义为：

```text
process-local cache
+
fast wakeup
+
shutdown drain
```

而不是：

```text
business authority
```

Final Gate 已确认 production 路径不存在：

```text
registry miss == inactive
registry registration == execution ownership
DB failure → fallback Registry
```

这种语义。

------

# 四、为什么使用 Lease，而不是永久 Owner

可以设计：

```text
run_id → owner=A
```

然后只有 A 主动释放以后别人才能执行。

问题是：

```text
A crash
```

之后没人能释放。

Run 永久卡死。

因此需要 Lease：

```text
owner=A
lease_until=22:30:00
```

A 需要周期：

```text
renew()
```

如果 A crash，lease 最终过期，B 才能 takeover。

当前 production scope 会：

```text
执行前 preflight renew
+
每 lease_seconds / 3 heartbeat renew
```

所以正常长 Run 不会因为 lease 自然过期而被另一个实例合法 takeover。

------

# 五、为什么 Lease 还不够

这是本 WP 最重要的知识点。

假设：

```text
A owns run
lease expires

B takeover
```

理论上 A 已经失去资格。

但是 Lease 无法让已经运行的 A：

```text
瞬间消失
```

例如 A 可能正在：

```text
HTTP call
thread pool
blocking Tool
GC pause
network partition
```

然后 A 恢复。

如果只判断：

```text
“我以前拿过 lease”
```

A 仍可能写数据库。

所以：

> Lease 解决“谁应该是 Owner”，Fencing Token 解决“旧 Owner 恢复以后怎么阻止它”。

------

# 六、Fencing Token 的核心原理

假设：

```text
A claim
token = 7
```

A 卡住。

lease expired。

B takeover：

```text
token = 8
```

之后所有受保护写入都必须携带：

```text
token
```

数据库检查：

```text
provided_token == current_token
```

于是：

```text
A:
token=7
→ reject

B:
token=8
→ allowed
```

Final Gate 实际验证了：

```text
A token=N
↓
B takeover token=N+1

A renew
→ OwnershipLost

A release
→ cannot release B

A terminal
→ rejected

A new Tool authorization
→ rejected before provider call
```

------

# 七、为什么 Fencing 必须在数据库事务里验证

错误实现：

```python
await run_control.assert_current(run_id, token)

# 中间发生 takeover

await journal.append_terminal(...)
```

第一步检查时：

```text
token=7
```

可能合法。

但是检查后：

```text
B takeover
token=8
```

然后 A 又继续 append terminal。

于是 stale executor 成功写入。

这就是 TOCTOU。

正确方式：

```text
BEGIN

lock / CAS
validate fencing token
write authoritative state

COMMIT
```

所有步骤必须共享同一个数据库事务边界。

------

# 八、为什么 Lease 用 PostgreSQL Time

错误设计：

```text
A local clock = 22:00:00
B local clock = 22:00:08
```

即便只有几秒 clock skew，也可能发生：

```text
A 认为 lease 还有效
B 认为 lease 已过期
```

于是 ownership 判断不一致。

WP1 使用：

```text
PostgreSQL now()
```

作为：

```text
lease_until
lease expiry
takeover
renew
```

的时间 Authority。

Application monotonic clock 只负责：

```text
什么时候发起下一次 heartbeat
```

而不决定 lease 是否有效。

------

# 九、为什么 terminal 不能只做“两次写”

最开始实施版本实际上留下了这个问题，Codex Gate 把它抓了出来。

错误：

```text
transaction 1:
Journal append RUN_COMPLETED
commit

transaction 2:
Run control CLOSED
commit
```

如果第二步失败：

```text
Journal:
COMPLETED

Control:
ACTIVE
```

系统出现两个事实互相矛盾。

反过来：

```text
Control:
CLOSED

Journal:
没有 terminal
```

也不行。

所以最后改成：

```text
BEGIN

fence validation

append RUN_COMPLETED journal

control.state = CLOSED
control.terminal_sequence = journal.sequence

COMMIT
```

任一步失败：

```text
ROLLBACK ALL
```

真实 PostgreSQL 测试验证了：

- Journal append 后失败 → 两者都 rollback；
- control close 注入失败 → 两者都 rollback；
- stale token → 两者都不写。

------

# 十、为什么 Journal 仍然是 Terminal Truth

虽然现在：

```text
runtime_run_control
```

中也存在：

```text
CLOSED
terminal_sequence
```

但它不能成为新的 Run terminal authority。

设计仍然是：

```text
Journal
= canonical terminal truth

Run Control
= execution coordination truth
```

也就是说：

```text
RunControl CLOSED
```

只表达：

> execution control 已经结束，并关联到了 terminal Journal sequence。

它不重新记录一份：

```text
SUCCESS / FAILURE / CANCELLED
```

否则就会形成：

```text
Journal terminal state
vs
RunControl terminal state
```

两个 Authority。

------

# 十一、跨实例 Cancel 是怎么工作的

现在：

```text
Run 在 instance A
```

cancel HTTP request 却可能打到：

```text
instance B
```

正确链路：

```text
B receives cancel

↓
authorization

↓
PostgreSQL durable CANCEL

↓ commit

↓
如果 B 本地也存在 RunHandle
    local fast wakeup
```

真正执行 Run 的 A：

```text
heartbeat / cancel poll
↓
发现 PostgreSQL cancel intent
↓
触发自己的 CancellationSource
```

因此：

```text
RunRegistry
```

只是：

```text
same-process fast path
```

而不是 cancellation truth。

Final Gate 还验证了：

```text
相同 cancel reason retry
→ 返回同一 durable intent

冲突 reason
→ fail closed
```

------

# 十二、为什么不用 Redis 做 Run Ownership

Redis 当然也能：

```text
SET NX PX
```

做分布式锁。

但当前项目已经有：

```text
PostgreSQL Journal
PostgreSQL Snapshot
Runtime persistence
transaction
advisory lock
```

而 WP1 还需要：

```text
lease
fencing
terminal Journal
control closure
```

在一个 transaction 中形成强一致边界。

如果用 Redis 做 ownership：

```text
Redis:
ownership truth

PostgreSQL:
terminal truth
```

就产生跨系统一致性问题。

因此 WP1 保持：

```text
PostgreSQL
= durable control authority

Redis
= cache / rate limit / optional wakeup
```

设计更简单，也更符合当前项目。

------

# 十三、为什么不用数据库 advisory lock 一直锁住整个 Run

一个直觉方案是：

```text
Run 开始
→ PostgreSQL advisory lock
→ 整个 Agent 执行期间不释放
```

问题包括：

- 长事务；
- 长连接占用；
- 数据库连接中断即语义复杂；
- 外部模型调用可能几十秒甚至更久；
- 无法自然表达 crash 后 takeover；
- 无法很好表达 stale executor。

所以 WP1 使用：

```text
short DB transaction
+
durable lease record
+
fencing token
```

而 advisory transaction lock 只用于：

```text
claim
cancel
finalize
```

等短事务中的并发串行。

------

# 十四、为什么不是分布式锁就结束

面试中很容易被问：

> 你这不就是加了个分布式锁吗？

不完全是。

单纯 Distributed Lock 通常只能回答：

```text
现在谁拿到了锁？
```

但 WP1 还需要解决：

```text
crash 后 takeover
stale executor
long-running renewal
cross-instance cancel
terminal atomicity
execution authorization
```

核心结构是：

```text
Lease
+
Fencing
+
Durable Command
+
Transactional Terminal
```

所以它比普通 mutex / lock 更接近：

> Agent Run Execution Ownership Protocol。

------

# 十五、工程方法类问答

## Q1：为什么不能只依赖 Lease？

因为 Lease 只能决定新的 Owner，不能强制杀死旧 Executor。旧 Executor 恢复后仍可能继续写，所以需要 monotonic Fencing Token 阻止 stale write。

------

## Q2：Lease 和 Fencing Token 分别解决什么问题？

Lease：

```text
谁现在应该拥有执行权
```

Fencing：

```text
旧 Owner 恢复以后，如何保证它不能再写
```

------

## Q3：为什么 Fencing Token 要单调递增？

这样新的 ownership generation 永远拥有更高 token。

数据库只需要判断：

```text
token == current generation
```

就能区分当前 executor 和 stale executor。

------

## Q4：为什么不能使用 UUID 当 Fencing Token？

UUID 可以区分 generation，但没有天然顺序。

单调 token 能直接表达：

```text
N+1 比 N 新
```

在 takeover、日志、诊断和数据库条件更新中更简单。

------

## Q5：为什么 Lease 时间用 DB time？

因为多个应用实例的本地 wall clock 可能存在偏差。

所有实例都依据同一个数据库时间判断 lease expiration，避免 clock skew 导致两个实例同时认为自己合法。

------

## Q6：为什么 terminal 要和 control close 同 transaction？

因为两者分别代表：

```text
Run 已经结束
```

和：

```text
execution ownership 已经关闭
```

如果分两次 commit，其中一次失败就会形成矛盾状态。

------

## Q7：为什么 Journal 仍然是 terminal truth，而不是 control table？

因为 Journal 原本就是 Runtime terminal Authority。

Run control 只用于协调谁可以执行。

如果 control table 也保存独立 terminal outcome，会重新制造第二 Authority。

------

## Q8：为什么 RunRegistry 没有删除？

因为 process-local cache 依然很有价值：

```text
低延迟 cancel
disconnect wakeup
shutdown drain
live handle lookup
```

问题不在于内存状态存在，而在于：

> 不能把内存状态当作 distributed truth。

------

## Q9：DB 挂了之后为什么要 fail closed？

因为 Runtime 已经无法证明：

```text
我仍然是合法 Owner。
```

继续执行可能导致另一个实例已经 takeover 后出现双执行。

因此 ownership uncertainty 必须被当成：

```text
lost authority
```

而不是普通网络 warning。

------

## Q10：为什么不用 Redis Lock？

当前项目的 terminal Journal、本次 Run control、fencing 都位于 PostgreSQL。

放在一个数据库里可以使用 transaction 构建更强、更简单的一致性边界，避免 Redis/PostgreSQL 双 Authority。

------

## Q11：为什么不直接上 Temporal？

因为需求只是：

```text
Agent Run execution ownership
```

不是：

```text
通用 durable workflow orchestration
```

引入 Temporal 会改变项目的 Runtime Owner，而且大幅提高复杂度。

我们只实现当前 Agent Harness 真正需要的最小 durable control plane。

------

# 十六、30 秒面试总结

我在 Agent Runtime 里解决过一个多实例执行所有权问题。原来 active Run 只存在进程内 RunRegistry，多实例下无法判断真正 Owner，也无法防止旧实例恢复后继续写。我后来把 Run control 放到 PostgreSQL，用单 Owner Lease 管执行权，用 DB time 做过期判断，并在每次 takeover 时递增 Fencing Token。所有关键写入都重新校验 token，stale executor 无法写 terminal 或继续申请新的 Tool execution。同时 cancel 也持久化，所以可以跨实例生效。最终 terminal Journal append 和 control close 在一个事务中完成，避免两个 Authority 状态不一致。

------

# 十七、2 分钟面试总结

我们原来的 Agent Runtime 是单进程设计，`RunRegistry` 保存 active Run，在一个实例里没有问题。但准备支持多实例后出现一个核心问题：一个请求落到 B 实例时，B 的内存里没有 Run，并不能说明这个 Run 没在 A 上执行。

所以我把执行所有权改成了 PostgreSQL durable control plane。每个 Run 同时只允许一个 active executor，通过 Lease 表示临时 ownership，lease 的时间判断使用 PostgreSQL `now()`，避免不同实例 clock skew。长 Run 会周期续租，lease 真正过期之后其他实例才允许 takeover。

但 Lease 本身还不够，因为旧 executor 可能在网络抖动、线程阻塞之后恢复。所以每一代 ownership 都会获得一个单调递增的 Fencing Token。比如 A 是 token 7，lease 过期后 B takeover 得到 token 8，那么 A 后续即使恢复，数据库也会拒绝它的 renew、terminal write 和新的 Tool authorization。

同时我们把 cancel 也改成 durable intent。Cancel 请求可以打到任意 API 实例，先写 PostgreSQL，然后真正执行 Run 的实例通过 heartbeat 观察它。原来的 RunRegistry 没删除，但只作为当前进程的快速唤醒 cache，不再是业务 Authority。

最后还有一个容易忽略的问题：Run 的 terminal Journal 和 control close 不能两个事务分别写，所以最终做成一个 PostgreSQL transaction，先验证 fencing token，再 append 唯一 terminal Journal，最后关闭 control aggregate。这样才能保证 terminal truth 和 execution ownership 一致。

------

# 十八、高频追问

## 1. 如果 Lease 已经过期，但旧实例其实还活着怎么办？

这正是 Fencing Token 的作用。

Lease expiration 允许新实例获得 ownership，Fencing Token 则保证旧实例即使活着，也无法再执行受保护写。

------

## 2. 你们怎么防止两个实例同时 claim？

`run_id` 有唯一 durable aggregate，并且 claim 使用 PostgreSQL transaction、advisory transaction lock 和条件更新。

真实 PostgreSQL 并发测试验证两个 service 同时 claim 时只有一个 current owner。

------

## 3. 如果 heartbeat 失败一次怎么办？

关键不是“网络失败了一次”，而是 Runtime 是否还能证明 ownership。

如果数据库无法证明 current ownership，就 fail closed，不能继续新的 protected action。

------

## 4. Cancel 为什么还要 polling？不能直接 RPC 给 Owner 吗？

直接 RPC 只能做优化。

如果 Owner 重启、路由表过期、网络断开，直接 RPC 会丢失。

所以 PostgreSQL durable cancel 才是真值，polling 保证最终可见，本地 RunRegistry wakeup 只是低延迟优化。

------

## 5. Polling 会不会性能差？

这里不是高频业务数据查询，而是每个 active Run 低频 control-plane check。

目前 cancel 最迟约 1 秒被观察，同时 lease heartbeat 周期是 lease duration 的一部分。

如果未来规模需要，可以用 Redis/Kafka notification 加速，但 PostgreSQL 仍保持 Authority。

------

## 6. Fencing Token 能防止已经发出去的 HTTP Tool 调用吗？

不能。

它能防止 stale executor 获得新的执行授权，也能阻止它写 authoritative result。

但已经到外部 Provider 的 side effect 不一定能撤回。

这正是 WP5 要进一步解决的：

```text
durable Tool invocation
UNKNOWN
idempotency
reconciliation
```

------

## 7. 现在支持 crash 后恢复整个 Agent 吗？

不支持。

WP1 解决的是：

```text
Run ownership
lease
fencing
cancel
terminal safety
```

不是 arbitrary execution resume。

后续 WP2 只会先补：

```text
WAITING_APPROVAL
```

附近的 durable recovery。

------

# 十九、Bad Case

## Bad Case 1：只做 Redis Lock

```text
SET run:123 owner=A NX PX 30000
```

问题：

```text
A 卡住
lock 过期
B 获得 lock
A 恢复
A 仍继续写
```

没有 Fencing，就不能阻止 stale executor。

------

## Bad Case 2：只做 Lease，没有 heartbeat

```text
lease = 30s

Agent Run = 2min
```

30 秒后 B 会合法 takeover，而 A 仍然正常运行。

Gate 最初就发现过这个问题并修复。

------

## Bad Case 3：Fencing 只在 Python 中判断

```text
assert_current(token)

# context switch
# B takeover

write_terminal()
```

典型 TOCTOU。

必须在目标 write transaction 内验证。

------

## Bad Case 4：RunRegistry miss 就返回 inactive

```text
request → instance B

B.registry.get(run_id)
→ None

return "run not active"
```

但 Run 其实在 A。

典型 process-local truth 被错误升级为 distributed truth。

------

## Bad Case 5：Cancel 只发内存事件

```text
B receives cancel
B registry miss
→ cancel lost
```

跨实例直接失效。

------

## Bad Case 6：Journal 和 control 分开提交

```text
Journal COMMITTED

Control close failed
```

系统同时存在：

```text
terminal
+
active execution control
```

出现 Authority 冲突。

------

## Bad Case 7：DB 出错继续执行

```python
try:
    renew()
except DatabaseError:
    logger.warning(...)
    continue_running()
```

这是危险实现。

因为另一个实例可能已经 takeover。

DB 无法证明 ownership 时必须 fail closed。

------

# 二十、这个 WP 最重要的三个面试知识点

如果时间有限，只记住三件事。

## 第一：Lease != Fencing

```text
Lease
解决谁应该执行。

Fencing
解决旧执行者为什么不能继续执行。
```

这是整个 WP 最关键概念。

------

## 第二：Memory 可以做 Cache，不能做 Distributed Authority

不是所有内存状态都必须删。

正确做法是：

```text
PostgreSQL = truth
RunRegistry = acceleration
```

------

## 第三：Authority 之间需要 Atomic Boundary

有两个相互关联的 durable fact：

```text
terminal Journal
control CLOSED
```

就必须考虑：

```text
如果第一个成功，第二个失败怎么办？
```

最终答案是：

```text
一个 transaction
```

------

# 二十一、Truth / Completion Boundary

## 已真实完成

### Durable Run Control

真实实现：

```text
PostgreSQL runtime_run_control
```

保存 durable ownership/control facts。

### Single Active Executor

一个 Run 同时只能有一个 current Owner。

### DB-time Lease

Lease creation、renew、expiry、takeover 使用 PostgreSQL time。

### Lease Renewal

Production Run 有 preflight renew + heartbeat renew。

### Monotonic Fencing

Takeover 后 token 严格递增。

### Stale Executor Rejection

stale executor 不能：

```text
renew
release new owner
write terminal
获得新的 Tool execution authorization
```

### Cross-instance Cancel

任意实例可以写 durable CANCEL，真正 executor 最终观察。

### Atomic Terminal

```text
fence validation
+
Journal RUN_COMPLETED
+
control CLOSED
```

同 transaction。

### RunRegistry Demotion

RunRegistry 只是 process-local cache / wakeup。

### Real PostgreSQL Integration

核心并发/事务行为使用真实 PostgreSQL 测试，而不是只靠 mock。

------

# 二十二、还没有完成

## Durable Approval

仍然 process-local。

这是 WP2。

## 任意 Agent Crash Resume

没有实现。

## Tool external side-effect exactly-once

没有实现。

## Tool UNKNOWN / Reconciliation

没有实现。

这是 WP5。

## 强制撤销已经发出去的外部 Tool 请求

做不到。

## Distributed Step Scheduling

没有实现，也不是当前目标。

## Cross-region Runtime

没有实现。

------

# 二十三、面试中不能夸大的表述

不要说：

> “我们实现了分布式 Agent Workflow Engine。”

应该说：

> “我们实现了 Agent Run 的 durable execution ownership。”

不要说：

> “我们已经支持任意 crash recovery。”

应该说：

> “Run ownership 可以 takeover，但任意 execution state resume 尚未实现。”

不要说：

> “Fencing 能保证外部 Tool exactly-once。”

应该说：

> “Fencing 能阻止 stale executor 获得新的执行权限，但已经发生的外部 side effect 需要幂等与 reconciliation。”

不要说：

> “RunRegistry 已经不需要了。”

应该说：

> “RunRegistry 被降级成 process-local fast path，不再拥有 distributed truth。”

------

# 二十四、一句话总结

> WP1 的本质不是“加数据库锁”，而是把 Agent Run 的执行所有权从进程内状态提升成 **Lease + Fencing + Durable Command + Transactional Terminal** 组成的持久化执行协议。