# Stage6-WP4 — Durable Async Job & Transactional Outbox

## 持久化异步任务与事务性发件箱学习 / 面试总结

------

# 1. 名词 / 概念速览

**持久化异步任务（Durable Async Job）**：任务状态保存在 PostgreSQL，而不是只存在进程内存中，因此服务重启后仍然存在。

**任务状态机（Job State Machine）**：限制 Job 可以发生哪些合法状态迁移。

**事务性发件箱（Transactional Outbox）**：业务数据与待发送事件写入同一个数据库事务，解决“数据库成功但消息没发出去”的双写问题。

**事务所有者（Transaction Owner）**：决定事务何时开始、提交、回滚的 Application Service。

**至少一次投递（At-Least-Once Delivery）**：消息可能重复，但不会因为特定 Crash Window 被永久遗漏。

**恰好一次（Exactly Once）**：每个业务事件只产生一次效果；当前 WP4 没有声称端到端 Exactly Once。

**条件更新（Conditional Update）**：通过 `WHERE status = expected` 让状态竞争在数据库里原子决胜。

**悲观行锁（Pessimistic Row Lock）**：通过数据库锁防止并发事务同时修改同一行。

**`FOR UPDATE SKIP LOCKED`**：锁住可处理的行，并跳过其他事务已经锁定的行，适合多 Publisher 并发 Claim。

**租约（Lease）**：某个 Publisher 在有限时间内拥有一个 Outbox Event 的处理权。

**Claim Token**：每次 Claim 生成的新 Identity，用于区分同一个 Publisher 对同一 Event 的不同 Claim 世代。

**栅栏令牌（Fencing Token）**：防止已经失效的旧 Owner 在迟到后覆盖新 Owner 的结果；本项目通过 fresh claim token 实现类似效果。

**数据库时间权威（Database Time Authority）**：Lease Deadline 与 Retry 时间基于 PostgreSQL `now()`，而不是依赖各个进程本地时钟。

**幂等（Idempotency）**：同一个逻辑操作重复执行，不产生额外副作用。

**ABA 问题（ABA Problem）**：资源从 A 状态变化后又回到看似相同的 A，旧持有者无法仅靠表面 Identity 判断所有权是否仍有效。

**双写问题（Dual Write Problem）**：业务数据库写入和消息系统发布无法由一个本地数据库事务原子覆盖。

**崩溃一致性（Crash Consistency）**：进程在任意关键步骤崩溃后，系统仍能恢复到一个可解释、可继续处理的状态。

------

# 2. 当前 WP 真实实现

WP4 建立了一条真实的 Durable Job 提交流程：

```text
Authenticated HTTP Request
        ↓
Principal.user_id
        ↓
EvaluationJobService
        ↓
PostgreSQL Transaction
        ├─ INSERT evaluation_jobs
        │     status = QUEUED
        │
        └─ INSERT outbox_events
              status = PENDING
        ↓
      COMMIT
```

Job 与 Outbox 必须一起成功或者一起失败。

Repository 本身不拥有 `commit()`、`rollback()` 或 Session Creation；事务由 Application Service 管理。

------

# 3. 为什么异步 Job 不能只放内存

最简单的后台任务可能是：

```python
asyncio.create_task(run_job())
```

但这类任务存在明显问题：

```text
HTTP 返回成功
↓
进程崩溃
↓
内存任务消失
```

WP4 的目标不是简单的 Background Task，而是：

```text
Job State
=
PostgreSQL Durable State
```

当前 Job Authority 明确是 PostgreSQL。

因此即使 API 进程重启：

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

这些业务状态不会因为进程退出而消失。

------

# 4. 当前 Job 状态机

数据库允许：

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

应用层只允许以下状态迁移：

```text
QUEUED → RUNNING

QUEUED → CANCELLED

RUNNING → SUCCEEDED

RUNNING → FAILED
```

当前明确不支持：

```text
RUNNING → CANCELLED
```

这不是遗漏，而是 Stage6 的 Scope 控制。

------

# 5. 为什么数据库 CHECK 不够

数据库：

```sql
CHECK (
  status IN (
    'QUEUED',
    'RUNNING',
    'SUCCEEDED',
    'FAILED',
    'CANCELLED'
  )
)
```

只能保证：

> status 是合法枚举值。

它不能阻止：

```text
SUCCEEDED → QUEUED
```

这种业务上非法的迁移。

所以真正的 Transition Contract 还要通过 Conditional Update：

```sql
UPDATE evaluation_jobs
SET status = 'RUNNING'
WHERE id = :job_id
AND status = 'QUEUED';
```

如果：

```text
affected_rows = 1
```

说明当前调用赢得状态迁移。

如果：

```text
affected_rows = 0
```

说明状态已经发生变化或不允许迁移。

------

# 6. Cancel 与 Start 为什么不会发生 TOCTOU Race

错误写法：

```text
SELECT status
↓
Python:
if status == QUEUED
↓
UPDATE status = RUNNING
```

与此同时另一个请求：

```text
SELECT status = QUEUED
↓
UPDATE status = CANCELLED
```

两个调用都可能基于旧状态判断成功。

当前实现让：

```text
Start
```

和：

```text
Cancel
```

都竞争：

```text
WHERE status='QUEUED'
```

所以数据库只允许一个更新成功。

最终只有：

```text
RUNNING
```

或：

```text
CANCELLED
```

其中一个合法结果。

------

# 7. Transactional Outbox 要解决什么问题

假设不用 Outbox。

方案 A：

```text
DB COMMIT
↓
Kafka publish
```

Crash Window：

```text
DB COMMIT 成功
↓
进程崩溃
↓
Kafka publish 没执行
```

结果：

```text
Job = QUEUED
Event = 永久缺失
```

未来 Worker 永远不知道该 Job 存在。

------

方案 B：

```text
Kafka publish
↓
DB COMMIT
```

Crash Window：

```text
Event 已发布
↓
DB transaction rollback
```

Worker 收到：

```text
job_id = X
```

但数据库里：

```text
Job X 不存在
```

两个系统之间没有一个普通本地事务可以同时覆盖：

```text
PostgreSQL
+
Kafka
```

所以 WP4 使用 Transactional Outbox。

------

# 8. Transactional Outbox 的核心思想

不直接要求：

```text
DB + Kafka
```

同时成功。

而是先把：

```text
Business State
+
Event Intent
```

都写到同一个 PostgreSQL Transaction。

当前 Submission：

```text
BEGIN

INSERT evaluation_jobs(...)

INSERT outbox_events(...)

COMMIT
```

任何一步异常：

```text
ROLLBACK BOTH
```

Final Review 已确认两个方向的 Failure 都有真实 PostgreSQL Fault Injection 验证。

------

# 9. Outbox 记录的是什么

Outbox 不是 Kafka Message 本身。

它本质上表示：

> “数据库已经确认，这个业务事件应该被发布。”

当前 Payload 非常小，只包含：

```text
schema version
event_id
job_id
```

不复制：

```text
query
Principal
JWT
credential
```

也就是说未来 Kafka Worker：

```text
收到 job_id
↓
重新查 PostgreSQL
↓
获得当前业务状态
```

而不是完全相信消息里的巨大 Payload。

------

# 10. Outbox 与 Job 的 Authority 是谁

Job：

```text
PostgreSQL evaluation_jobs
=
Job Authority
```

Outbox：

```text
PostgreSQL outbox_events
=
Pending Event Authority
```

未来 Kafka：

```text
Kafka
=
Transport
```

不是业务状态 Authority。

这三个角色不能混淆。

------

# 11. 为什么 Outbox Publisher 需要 Claim

假设同时运行：

```text
Publisher A
Publisher B
```

如果两者都执行：

```sql
SELECT * FROM outbox_events
WHERE published = false;
```

然后分别 Publish：

同一个 Event 很容易被两个 Publisher 同时发送。

所以需要：

```text
Claim
```

表示：

> 当前由哪个 Publisher 暂时负责这个 Event。

------

# 12. 为什么使用 FOR UPDATE SKIP LOCKED

当前 Claim：

```text
SELECT ...
FOR UPDATE SKIP LOCKED
LIMIT ...
```

再更新 Claim 信息。

假设：

```text
Event 1
Event 2
Event 3
```

Publisher A：

```text
lock Event 1
```

Publisher B：

```text
看到 Event 1 已锁
→ SKIP
→ claim Event 2
```

这意味着多个 Publisher：

```text
不必互相等待
```

又不会：

```text
同时 Claim 同一个 Event
```

适合数据库 Queue / Outbox Polling。

------

# 13. 为什么不是 SELECT 后再 UPDATE

错误方案：

```text
Publisher A SELECT event 1
Publisher B SELECT event 1

A UPDATE claim_owner=A
B UPDATE claim_owner=B
```

存在明显 Race Window。

而：

```text
FOR UPDATE SKIP LOCKED
```

把“发现待处理 Row”和“获取排他处理权”放入数据库锁语义中。

------

# 14. Claim 为什么还需要 Lease

如果 Claim 是永久的：

```text
Publisher A claims Event 1
↓
Publisher A crashes
```

Event 1 永久处于：

```text
claimed
```

没人再处理。

因此 Claim 必须有：

```text
claim_deadline
```

当前基于：

```text
PostgreSQL now()
```

Lease 到期以后：

```text
其他 Publisher
→ reclaim
```

------

# 15. 为什么 Lease 使用数据库时间

假设两个 Publisher：

```text
Server A clock = 12:00:02
Server B clock = 11:59:58
```

如果各自用：

```python
datetime.now()
```

计算：

```text
lease expired?
```

可能得到不同答案。

当前使用：

```text
PostgreSQL now()
```

作为统一时间 Authority。

和 WP3 Rate Limiter 使用 Redis TIME 的思想类似：

> 分布式协调状态尽量让共享 Authority 自己提供时间。

------

# 16. 为什么只有 claim_owner 还不够

假设 Publisher：

```text
publisher-1
```

第一次 Claim：

```text
Event X
claim_owner = publisher-1
```

然后：

```text
lease expires
```

同一个 Publisher Process Identity 后来又重新 Claim：

```text
claim_owner = publisher-1
```

从字段看：

```text
before = publisher-1
after  = publisher-1
```

无法判断旧操作还是新操作。

这就是实施阶段发现的 ABA 风险。

因此每次 Claim 都增加：

```text
fresh claim_token
```

Final Review 已确认这一机制。

------

# 17. Claim Token 如何形成 Fencing

场景：

```text
Publisher A
claim Event X
token = T1
```

A 卡住。

之后：

```text
Lease T1 expires
```

Publisher B Claim：

```text
token = T2
```

这时候 A 的外部 Publish 才返回。

如果 A 尝试：

```text
mark published
```

数据库检查：

```text
event_id = X
owner = A
token = T1
claim_deadline > now()
```

已经不满足。

所以：

```text
A stale mark
→ rejected
```

B 的：

```text
token = T2
```

才拥有当前合法权利。

这就是 Fencing 的作用。

------

# 18. 为什么 Publisher 不能在数据库事务里 Publish

错误：

```text
BEGIN

SELECT FOR UPDATE
↓
Kafka publish
↓
等待网络
↓
mark published

COMMIT
```

可能导致：

```text
DB Connection 长时间占用
Row Lock 长时间持有
网络抖动扩大 Transaction Duration
其他 Publisher 被阻塞
```

当前边界：

```text
TX1
Claim
Commit

↓

External Publish

↓

TX2
Mark Published / Retry
Commit
```

Final Review 已确认 External EventSink 在数据库事务之外调用。

------

# 19. 这样做为什么会产生重复消息

现在：

```text
Publish
```

和：

```text
Mark Published
```

不在一个事务。

场景：

```text
Kafka publish succeeded
↓
process crash
↓
Mark Published 没执行
```

数据库仍认为：

```text
event not published
```

恢复后：

```text
publish again
```

于是重复消息。

所以当前系统明确：

```text
AT_LEAST_ONCE
```

------

# 20. 为什么这不是 Bug

因为解决 Dual Write 后，一般可靠消息系统更实际的目标是：

```text
不丢
+
允许重复
+
Consumer 幂等
```

而不是虚假声称：

```text
永远只发一次
```

WP4 明确接受：

```text
same event_id
may be delivered again
```

WP5 再通过：

```text
Consumer Dedup
+
Idempotent Business Effect
```

处理重复。

当前 source 只支持 At-Least-Once；Consumer Dedup 尚未实现，属于 WP5。

------

# 21. Event ID 为什么 Retry 时不能重新生成

第一次 Publish：

```text
event_id = E1
```

Crash。

Retry 如果生成：

```text
event_id = E2
```

Consumer 看起来就是：

```text
两个完全不同的业务事件
```

以后无法可靠 Dedup。

当前：

```text
event_id
```

在 Outbox 创建时固定。

Retry / Reclaim / Republish：

```text
same event_id
```

这给 WP5 Consumer Dedup 提供了稳定 Identity。

------

# 22. Cancel 后为什么不删除 Outbox Event

场景：

```text
Job = QUEUED
Outbox queued event already published
```

此时用户 Cancel：

```text
QUEUED → CANCELLED
```

你已经不可能保证：

```text
Kafka Event
```

能被撤回。

所以真正正确的 Contract 不是：

```text
Cancel
→ 删除所有事件
```

而是：

```text
Worker receives queued event
↓
load Job from PostgreSQL
↓
check current status
↓
CANCELLED
→ do nothing
```

也就是说：

```text
Message
=
Trigger

PostgreSQL Job State
=
Execution Authority
```

Final Review 明确确认 Outbox Event 不因取消而删除。

------

# 23. Result Finalization 为什么也要事务

错误情况：

```text
UPDATE job = SUCCEEDED
COMMIT

↓

INSERT result
失败
```

最终：

```text
Job = SUCCEEDED
Result = missing
```

业务状态自相矛盾。

所以当前：

```text
BEGIN

RUNNING → SUCCEEDED

INSERT evaluation_results

COMMIT
```

Result Insert 失败：

```text
整个事务 rollback
```

Job 保持：

```text
RUNNING
```

------

# 24. Duplicate Finalization 怎么处理

当前：

```text
evaluation_results.job_id
UNIQUE
```

并结合 Result Digest。

重复完成：

```text
same result digest
```

视为：

```text
idempotent replay
```

但如果：

```text
different result digest
```

则：

```text
JOB_STATE_CONFLICT
```

这避免：

```text
同一个 Job
→ 两份不同 Final Result
```

------

# 25. 为什么数据库约束和 Application Logic 都要有

Application Service：

```text
避免正常路径产生错误行为
```

Database Constraint：

```text
提供最终一致性保护
```

例如：

```text
UNIQUE(job_id)
```

能在并发、Bug 或重复调用情况下继续守住：

```text
一个 Job
最多一个 Final Result
```

这是典型的：

> Application Guard + Database Invariant。

------

# 26. Job Ownership 怎么做

当前：

```text
owner_user_id
=
server-verified Principal.user_id
```

Caller 不允许提交 Owner。

USER：

```text
只能访问自己的 Job
```

ADMIN：

```text
复用 AuthorizationService
```

而不是重新造一套 Job 权限系统。

------

# 27. Hidden 404 为什么重要

Final Review 实际发现：

```text
访问别人 Job
```

和：

```text
Job 不存在
```

虽然都是 404，但原来的：

```text
error code / message
```

不同。

攻击者仍然可以通过响应差异判断：

> 某个 Job ID 是否真实存在。

修复后：

```text
status
error code
message
```

完全一致，都映射：

```text
JOB_NOT_FOUND
```

这是典型的：

```text
Resource Enumeration
```

防护。

------

# 28. Retry Backoff 为什么也会有 Bug

Final Review 发现：

```text
Backoff
+
Jitter
```

之后可能突破：

```text
retry_max_seconds
```

比如：

```text
max = 60s

base backoff = 60s
jitter = +8s
```

结果：

```text
68s
```

违背最大值 Contract。

修复后：

```text
apply jitter
↓
clamp to max
```

同时拒绝：

```text
NaN
Infinity
```

这种非有限值绕过配置校验。

------

# 29. 工程构建方法类问答

## Q1：为什么需要 Transactional Outbox？

因为数据库事务无法原子覆盖 PostgreSQL 和 Kafka 两个系统，直接“双写”存在 crash window。Outbox 先把业务状态和 Event Intent 放进同一个本地数据库事务。

------

## Q2：Outbox 能保证 Exactly Once 吗？

不能。Publish 成功但 Mark 前 Crash 会再次 Publish，所以是 At-Least-Once。

------

## Q3：那重复消息怎么办？

通过稳定 event_id、Consumer Dedup 和业务幂等解决。Consumer 部分属于 WP5。

------

## Q4：为什么用 `FOR UPDATE SKIP LOCKED`？

让多个 Publisher 可以并发从同一 Outbox 表获取不同任务，同时避免同时 Claim 同一行。

------

## Q5：为什么还需要 Lease？

Publisher Claim 后可能崩溃；没有 Lease，Event 会永久卡住。

------

## Q6：为什么 Lease 使用 PostgreSQL 时间？

避免不同 Publisher 主机时钟漂移导致对 Lease Expiry 判断不同。

------

## Q7：为什么 claim_owner 不够？

同一个 Publisher Identity 可能在 Lease 过期后再次 Claim，产生 ABA。Fresh Claim Token 可以区分 Claim 世代。

------

## Q8：Fencing 解决什么问题？

阻止已经失去 Lease 的旧 Publisher 在迟到后修改新 Owner 已接管的状态。

------

## Q9：为什么外部 Publish 不能放在 DB Transaction 里？

外部网络调用时间不可控，会长时间持有数据库事务、连接和行锁。

------

## Q10：为什么 Cancel 不删除 Outbox？

Event 可能已经发布，无法可靠撤回。真正执行与否必须以 PostgreSQL 当前 Job State 为 Authority。

------

# 30. 30 秒面试回答

我在 LocalAgent 里做了一套 PostgreSQL Durable Job 和 Transactional Outbox。创建 Evaluation Job 时，不是先写数据库再直接发消息，而是在同一个数据库事务里同时写 `evaluation_jobs` 和 `outbox_events`，这样不会出现 DB 提交成功但事件丢失的双写窗口。

Publisher 用 `FOR UPDATE SKIP LOCKED` 并发 Claim Outbox，通过 PostgreSQL 时间做 Lease，每次 Claim 生成新的 Token 做 Fencing。外部 Publish 不放在数据库事务里，Publish 成功但 Mark 前 Crash 时允许同一个 event_id 重投，所以语义明确是 At-Least-Once。后续 Kafka Consumer 再通过 event_id Dedup 和业务幂等处理重复。

------

# 31. 2 分钟面试回答

我把 Evaluation 执行从同步请求模型拆成了 PostgreSQL 持久化 Job。Job 有 QUEUED、RUNNING、SUCCEEDED、FAILED、CANCELLED 五个状态，所有迁移用条件 UPDATE，例如 Start 和 Cancel 都竞争 `status=QUEUED`，因此两个并发请求只能一个成功。

消息可靠性这块用了 Transactional Outbox。创建 Job 时，`evaluation_jobs` 和 `outbox_events` 在同一个 Application Service Transaction 里提交。如果 Job Insert 或 Outbox Insert 任何一个失败，整个事务回滚，所以不会出现业务数据存在但消息意图不存在的问题。

Publisher 通过 `FOR UPDATE SKIP LOCKED` Claim Outbox Row，并使用 PostgreSQL `now()` 作为 Lease 时间源。只用 `claim_owner` 会有 ABA，所以每次 Claim 还生成新的 Claim Token。Mark Published 时必须同时匹配 Event ID、Owner、Token 和未过期 Lease，这样旧 Publisher 即使迟到也不能覆盖新的 Owner。

Publisher 的数据库事务只负责 Claim 和 Mark，真正外部 Publish 在事务之外完成，因此不会长时间持有数据库 Row Lock。代价是 Publish 成功但 Mark 之前 Crash 会再次投递，所以系统明确采用 At-Least-Once，不声称 Exactly Once。下一阶段接 Kafka 后，再用稳定 event_id 做 Consumer Dedup。

------

# 32. 高频追问 + 简答

### Outbox 和 Kafka 有什么区别？

Outbox 是 PostgreSQL 中尚待发布的业务事件 Authority；Kafka 是外部消息 Transport。

### 为什么 Outbox 不能直接替代 Kafka？

当前 Outbox 是数据库 Polling 模型，不是用于大规模消息分发和 Consumer Group 的消息基础设施。

### `SKIP LOCKED` 会不会漏任务？

当前查询只是暂时跳过其他事务持有的锁；后续 Poll 仍可看到未发布的 Event。

### Publisher Crash 后任务怎么办？

Lease 到期后其他 Publisher 可以 Reclaim。

### 为什么需要 Claim Token？

防止旧 Claim 和新 Claim Owner Identity 相同产生 ABA。

### 为什么不用 Distributed Lock？

Outbox Row Claim 已由 PostgreSQL Row Lock、Conditional Update、Lease 与 Token Fencing 管理，不需要再引入 Redis Lock。

### 为什么不支持 RUNNING Cancel？

这是当前 Scope Boundary；运行中取消需要 Worker Cooperative Cancellation、执行中断和更多状态语义，留到以后。

### Result 为什么还需要 Digest？

用于判断重复 Finalization 是同一结果的幂等重放，还是不同结果的冲突。

------

# 33. Bad Case / Failure Scenario

## Bad Case 1：先 Commit Job，再 Publish

```text
INSERT Job
COMMIT
↓
CRASH
↓
Publish 没执行
```

结果：

```text
Job 永久没人消费
```

正确：

```text
Job + Outbox
same transaction
```

------

## Bad Case 2：先 Publish，再 Commit Job

```text
Publish Event
↓
DB rollback
```

Worker：

```text
拿到不存在的 job_id
```

------

## Bad Case 3：只有 claim_owner

```text
Publisher A owner=A token implicit
↓
lease expiry
↓
Publisher A later reclaims owner=A
```

旧请求和新 Claim 无法区分。

正确：

```text
fresh claim_token
```

------

## Bad Case 4：Publish 放在 DB Transaction

```text
BEGIN
lock row
↓
Kafka timeout 20s
```

结果：

```text
Transaction 长时间占用
Row Lock 长时间占用
DB Pool 压力增大
```

------

## Bad Case 5：误称 Exactly Once

```text
publish success
↓
crash
↓
not marked
↓
republish
```

说明重复天然可能发生。

真实语义：

```text
At-Least-Once
```

------

## Bad Case 6：Cancel 后假设 Event 一定能删除

Event 可能已经进 Kafka。

正确模型：

```text
Worker
→ load PostgreSQL Job
→ CANCELLED
→ skip
```

------

## Bad Case 7：先把 Job 标成 SUCCEEDED 再存 Result

Result Insert Fail：

```text
SUCCEEDED
+
no result
```

正确：

```text
Job transition + Result insert
same transaction
```

------

# 34. Truth Boundary

当前真实实现：

```text
✅ PostgreSQL Durable Evaluation Job

✅ QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED

✅ Conditional State Transition

✅ Principal-derived Job Ownership

✅ Transactional Outbox

✅ Job + Outbox Same Transaction

✅ Immutable Event ID

✅ Versioned Minimal Outbox Payload

✅ FOR UPDATE SKIP LOCKED

✅ Database-time Lease

✅ Fresh Claim Token

✅ Stale Publisher Fencing

✅ Bounded Retry / Backoff

✅ Publish Outside DB Transaction

✅ At-Least-Once Semantics

✅ Result Finalization Transaction

✅ UNIQUE(job_id)

✅ Same Digest Idempotency

✅ Different Digest Conflict

✅ Hidden 404

✅ Real PostgreSQL Integration Test
```

Final Review 已确认这些 Contract。

尚未实现：

```text
❌ Kafka Producer

❌ Kafka Consumer

❌ Consumer Dedup

❌ DLQ

❌ Real Evaluation Kafka Worker

❌ RUNNING Cancellation

❌ Parallel Publisher Pipeline

❌ Lease Renewal

❌ End-to-End Exactly Once
```

------

# 35. Completion Boundary

最终：

```text
WP4_REVIEW_STATUS = PASS

JOB_POSTGRESQL_AUTHORITY_CONFIRMED = YES
JOB_LIFECYCLE_CONFIRMED = YES
JOB_OWNER_CONFIRMED = YES

JOB_OUTBOX_ATOMICITY_CONFIRMED = YES

OUTBOX_POSTGRESQL_AUTHORITY_CONFIRMED = YES
OUTBOX_EVENT_IDENTITY_CONFIRMED = YES

SKIP_LOCKED_CLAIM_CONFIRMED = YES
LEASE_CONFIRMED = YES
DATABASE_TIME_AUTHORITY_CONFIRMED = YES

CLAIM_TOKEN_FENCING_CONFIRMED = YES
STALE_PUBLISHER_BLOCKED = YES

PUBLISH_OUTSIDE_DB_TRANSACTION_CONFIRMED = YES

AT_LEAST_ONCE_CONFIRMED = YES

CANCEL_CONCURRENCY_CONFIRMED = YES

RESULT_ATOMICITY_CONFIRMED = YES
DUPLICATE_FINALIZATION_CONFIRMED = YES

REAL_POSTGRESQL_EVIDENCE_CONFIRMED = YES

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0

CAN_CLOSE_WP4 = YES
CAN_ENTER_WP5 = YES
```

------

# 36. Known Limitation / ACCEPTED_P1

当前限制：

```text
Kafka Producer / Consumer = WP5

Consumer Dedup = WP5

DLQ = WP5

RUNNING Cancellation = NO

Publisher Parallel Pipeline = NO

Lease Renewal = NO

Encrypted Request Reference Store = NO

End-to-End Exactly Once = NO
```

Final Review 中：

```text
ACCEPTED_P1 = 0
```

说明这些都是 Scope / Known Limitation，而不是当前 WP 的未关闭缺陷。

------

# 37. 面试关键词

优先掌握：

```text
Durable Job

Job State Machine

Conditional Update

Transactional Outbox

Dual Write Problem

Application-owned Transaction

At-Least-Once Delivery

Exactly Once

Idempotency

FOR UPDATE

SKIP LOCKED

Lease

Database Time Authority

Claim Token

Fencing

ABA Problem

Crash Consistency

Publisher

Outbox Polling

Retry Backoff

Jitter

Event Identity

Consumer Dedup

Result Finalization

Database Constraint

Resource Enumeration

Hidden 404
```

------

# 38. WP3 与 WP4 可以串起来怎么讲

WP3：

```text
Redis
→ Cache / Traffic Governance
```

解决：

```text
性能
流量控制
```

WP4：

```text
PostgreSQL Durable Job
+
Transactional Outbox
```

解决：

```text
异步任务持久化
跨系统消息可靠性
Crash Consistency
```

所以现在后端主线已经逐渐形成：

```text
HTTP API
↓
Authentication / Authorization
↓
Redis Traffic Governance
↓
PostgreSQL Durable Job
↓
Transactional Outbox
↓
[WP5 Kafka]
↓
Worker
```

------

# 39. 本 WP 最值得掌握的 8 个问题

时间有限时优先吃透：

```text
1. 什么是 Dual Write Problem，为什么需要 Transactional Outbox？

2. 为什么 Job 和 Outbox 必须在同一个数据库事务？

3. 为什么 Outbox Publisher 使用 FOR UPDATE SKIP LOCKED？

4. 为什么 Claim 除了 Owner 还需要 Lease 和 Fresh Token？

5. 什么是 ABA，Claim Token 如何实现 Fencing？

6. 为什么 External Publish 必须放在数据库事务之外？

7. 为什么 Transactional Outbox 最终仍然是 At-Least-Once？

8. Cancel、Worker Execution 与 PostgreSQL Job Authority 应该如何配合？
```

最值得记住的一句话：

> **Transactional Outbox 不是让数据库和消息队列“同时提交”，而是先把业务状态和“必须发送这条消息”这个事实原子地提交到同一个数据库，再允许 Publisher 以 At-Least-Once 的方式可靠地把它送出去。**