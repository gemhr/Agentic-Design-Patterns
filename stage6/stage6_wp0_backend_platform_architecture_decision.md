# Stage6-WP0 — Backend Platform Architecture Decision

## 后端平台架构决策学习 / 面试总结

------

# 1. 名词 / 概念速览

**规范实现（Canonical Implementation）**：当前系统唯一被认可的正式实现路径，Legacy 或旧实现不再天然享有兼容权。

**数据权威（Data Authority）**：某类业务事实最终以哪个组件或存储作为唯一可信来源。

**组合根（Composition Root）**：负责应用级依赖创建、装配和生命周期管理的位置，LocalAgent 当前由 `server.py::lifespan()` 承担。

**异步数据库引擎（Async Database Engine）**：以异步 I/O 方式访问数据库，避免在 ASGI 事件循环中直接执行不可控的同步数据库操作。

**连接池（Connection Pool）**：预先维护一组数据库连接供请求复用，避免频繁建立连接，并对数据库并发形成容量边界。

**工作单元（Unit of Work, UoW）**：把多个 Repository 操作组织在同一个业务事务中的模式。

**事务边界（Transaction Boundary）**：明确事务在哪里 BEGIN、COMMIT、ROLLBACK，以及哪个组件拥有事务控制权。

**事务发件箱模式（Transactional Outbox Pattern）**：把业务状态和“待发送消息”写入同一个数据库事务，避免数据库与消息队列双写不一致。

**双写一致性问题（Dual-write Consistency Problem）**：数据库和 Kafka 分别写入时，其中一个成功、另一个失败导致状态不一致的问题。

**至少一次投递（At-least-once Delivery）**：消息可能重复，但不能因为常规故障静默丢失，因此消费者必须具备幂等能力。

**幂等消费者（Idempotent Consumer）**：同一事件重复消费时，不会重复产生业务副作用。

**消费者组（Consumer Group）**：Kafka 中多个消费者协作消费 Topic Partition 的机制。

**偏移量（Offset）**：Kafka Partition 中消息的位置，用于记录消费者消费进度。

**分区键（Partition Key）**：决定 Kafka 消息进入哪个 Partition 的 Key，并影响局部顺序保证。

**死信队列（Dead Letter Queue, DLQ）**：用于隔离经过重试仍无法正常处理的异常消息。

**主体（Principal）**：服务端经过认证后得到的可信用户身份，而不是客户端自行传入的 `actor_id`。

**基于角色的访问控制（Role-Based Access Control, RBAC）**：根据 USER、OPERATOR、ADMIN 等角色控制允许执行的操作。

**缓存旁路模式（Cache-Aside）**：应用先读缓存，Miss 时读取真实数据源并回填缓存；缓存本身不成为 Authority。

**令牌桶（Token Bucket）**：通过令牌生成和消费控制请求速率的限流算法。

**分布式追踪（Distributed Tracing）**：将 HTTP、数据库、Redis、Kafka、Worker 等跨进程调用串成完整 Trace。

**W3C Trace Context**：跨 HTTP/MQ 等边界传播 Trace 信息的标准格式。

**优雅关闭（Graceful Shutdown）**：停止接收新任务后，对正在执行的事务、消息和资源进行有界 Drain，再释放连接与进程。

------

# 2. 本 WP 真实完成了什么

WP0 没有修改生产代码。

真正完成的是：

> 为 Stage6 后续所有后端基础设施建设冻结 Architecture、Owner、Authority、Contract 和进程边界。

最终架构确定为：

```text
PostgreSQL
+ Redis
+ Kafka
+ FastAPI
+ JWT / RBAC
+ Prometheus
+ OpenTelemetry
+ Docker Compose
+ Kubernetes
```

但当前只有架构决策完成。

PostgreSQL、Redis、Kafka、Outbox、JWT、Docker、Kubernetes 等还没有在 WP0 中实际实现。

最终 PostgreSQL 技术选型被冻结为：

```text
PostgreSQL
SQLAlchemy 2.x Async ORM + Core
asyncpg
Alembic
```

关系型数据最终统一迁移至 PostgreSQL：

```text
Memory
Runtime Journal
Snapshot
Checkpoint
User / Role / Principal
Evaluation Job / Result
Outbox
Consumer Dedup
```

SQLite 不再作为生产运行时关系型 Authority，也不保留 PostgreSQL/SQLite 双写和运行时 fallback。

------

# 3. Stage6 最终架构

冻结后的后端结构：

```text
Client
  │
  │ JWT
  ▼
localagent-api
  │
  ├── Authentication / RBAC
  │
  ├── Redis Rate Limiter
  │
  └── RAG Cache
  │
  ▼
Application Service
  │
  ▼
PostgreSQL
  ├── Memory
  ├── Runtime Journal
  ├── Snapshot
  ├── Checkpoint
  ├── User / Role
  ├── Evaluation Job
  ├── Evaluation Result
  ├── Outbox
  └── Consumer Dedup
        │
        ▼
outbox-publisher
        │
        ▼
Kafka
evaluation.jobs.v1
        │
        ▼
evaluation-worker
        │
        ▼
PostgreSQL
```

API、Publisher、Worker 被明确拆成三个独立进程。

```text
localagent-api
outbox-publisher
evaluation-worker
```

Publisher 不塞进 FastAPI lifespan，Worker 也不由 Uvicorn worker 数量隐式控制。

------

# 4. PostgreSQL 为什么成为唯一关系型 Authority

Stage6 没有选择：

```text
SQLite
+
额外 PostgreSQL Job DB
```

因为这样会形成两个关系数据库平台，并增加：

```text
事务无法跨库
双 Authority
双 Migration
双测试体系
双生命周期
```

特别是：

```text
SQLite business fact
        ↓
PostgreSQL Outbox
```

无法放进同一个事务。

最终决定：

```text
All relational persistence
        ↓
PostgreSQL
```

而：

```text
Chroma
```

继续只负责 Vector / Retrieval Index。

因此数据边界是：

```text
PostgreSQL = relational facts
Chroma     = knowledge index
Redis      = temporary acceleration / traffic control
Kafka      = event delivery
```

这也是一个非常典型的后端架构原则：

> 不同基础设施应该承担不同数据语义，而不是因为都能存数据就互相替代。

------

# 5. 为什么使用 SQLAlchemy Async + asyncpg

WP0 没有选择纯：

```text
asyncpg + handwritten SQL
```

而是：

```text
SQLAlchemy Async ORM + Core
        ↓
asyncpg
```

原因是需要同时解决：

```text
Model Mapping
Repository
Transaction
Connection Pool
Migration
复杂 SQL
```

SQLAlchemy ORM 可以负责普通领域对象映射。

复杂操作，例如：

```text
Outbox Claim
Bulk Update
SELECT ... FOR UPDATE SKIP LOCKED
```

则使用 SQLAlchemy Core。

因此不是：

> ORM everything。

而是：

> ORM 和 Core 根据场景组合使用。

同时 Repository 被明确设计成窄接口：

```text
JobRepository
ResultRepository
OutboxRepository
IdentityRepository
RuntimePersistence
```

禁止造一个万能：

```text
BaseRepository<T>
```

Framework。

------

# 6. Transaction Owner 为什么必须是 Application Service

最终事务模型：

```text
HTTP Route
    ↓
Application Service
    ↓
async with session.begin()
    ↓
Repository
```

Route：

```text
认证
DTO
HTTP projection
```

Service：

```text
业务逻辑
事务
```

Repository：

```text
SQL / persistence
```

其中只有 Application Service 能：

```text
BEGIN
COMMIT
ROLLBACK
```

Repository：

```text
不得 commit()
不得 rollback()
不得私自创建 Session
```

原因是 Repository 不知道完整业务操作包含几个数据修改。

例如创建 Evaluation Job：

```text
INSERT evaluation_jobs
INSERT outbox_events
```

这两个动作是一个业务操作。

如果：

```text
JobRepository.commit()
↓
OutboxRepository.insert()
↓
失败
```

就重新制造了 Dual-write Problem。

因此：

```text
Application Service
     │
     └── Transaction Owner
```

非常关键。

------

# 7. Durable Evaluation Job 为什么成为 Stage6 主业务

Stage6 需要一个真正能承载：

```text
Database
Kafka
Outbox
Worker
Retry
Idempotency
Observability
```

的业务对象。

最终选择：

```text
Evaluation Job
```

生命周期：

```text
QUEUED
   ↓
RUNNING
   ↓
SUCCEEDED
FAILED
CANCELLED
```

其中用户取消只支持：

```text
QUEUED → CANCELLED
```

Job 的业务 Owner 是：

```text
creating Principal
```

Worker 只是：

```text
execution owner
```

不是业务事实 Owner。

这种区分很重要：

```text
Job state = PostgreSQL business fact

Kafka message = delivery fact

Kafka offset = consumer progress

Metrics / Trace = observation fact
```

它们不能互相代替。

------

# 8. Transactional Outbox 为什么是核心设计

最简单的错误实现：

```text
BEGIN

INSERT evaluation_job

COMMIT

Kafka.publish()
```

存在一个经典故障：

```text
DB COMMIT 成功
        ↓
进程 crash
        ↓
Kafka 没发
```

Job 永远留在数据库：

```text
QUEUED
```

但 Worker 永远不知道有这个 Job。

Transactional Outbox 改成：

```text
BEGIN

INSERT evaluation_job

INSERT outbox_event

COMMIT
```

两者：

```text
要么都存在
要么都不存在
```

然后：

```text
outbox-publisher
```

独立扫描：

```text
published_at IS NULL
```

的数据并发送 Kafka。

因此数据库事务负责：

```text
业务事实
+
发送意图
```

Kafka Publisher 只负责：

```text
Delivery
```

而不拥有 Job 状态。

------

# 9. Outbox Publisher 为什么使用 SKIP LOCKED

未来可以启动多个 Publisher：

```text
Publisher A
Publisher B
Publisher C
```

如果它们同时查询：

```sql
SELECT *
FROM outbox_events
WHERE published_at IS NULL;
```

可能同时拿到同一事件。

最终采用：

```sql
SELECT ...
FOR UPDATE SKIP LOCKED
```

逻辑相当于：

```text
Publisher A lock row 1
Publisher B 看到 row 1 被锁
            ↓
          skip
            ↓
          row 2
```

同时使用：

```text
claim_owner
claim_deadline
```

构建 Lease。

如果 Publisher A：

```text
claim
 ↓
crash
```

Lease 到期后：

```text
Publisher B reclaim
```

因此可以恢复，而不是事件永久卡死。

------

# 10. 为什么 Outbox 仍然是 At-least-once

即使有 Outbox：

```text
Kafka publish success
        ↓
Publisher crash
        ↓
published_at 没写成功
```

数据库仍认为：

```text
unpublished
```

重启后会重新 publish。

因此：

```text
duplicate message
```

是正常情况。

所以系统没有承诺：

```text
Exactly-once Delivery
```

而是：

```text
At-least-once Delivery
+
Idempotent Consumer
```

这也是更加真实的分布式系统设计。

------

# 11. Idempotent Consumer 是怎么设计的

Kafka Consumer 收到：

```text
event_id = E1
```

执行：

```text
BEGIN

INSERT consumer_processed_events
(
    consumer_name,
    event_id
)

UPDATE evaluation_job

INSERT evaluation_result

COMMIT

Kafka offset commit
```

其中数据库有：

```text
UNIQUE
(consumer_name, event_id)
```

考虑故障：

```text
DB COMMIT 成功
        ↓
Consumer crash
        ↓
offset 没 commit
```

Kafka 会再次发送 E1。

第二次：

```text
INSERT consumer_processed_events
```

发生唯一键冲突。

系统知道：

```text
E1 已经完成业务事务
```

因此：

```text
不重新写 Result
只推进 offset
```

最终得到：

```text
消息可能重复
业务效果不重复
```

WP0 把这种语义称为：

> business-effect exactly-once-like

而明确不是任意外部副作用的端到端 Exactly-once。

------

# 12. Kafka 为什么按 job_id 分区

Topic：

```text
evaluation.jobs.v1
```

Partition key：

```text
job_id
```

因此：

```text
Job A event1
Job A event2
Job A event3
```

能够进入同一个 Partition。

Kafka 能保证的顺序：

```text
同一个 Partition 内
```

而不是：

```text
整个 Topic 全局有序
```

不同 Job：

```text
Job A
Job B
```

可以并行处理。

这样兼顾：

```text
单 Job 局部顺序
+
Job 间吞吐
```

Kafka Consumer Group：

```text
localagent-evaluation-worker-v1
```

Offset：

```text
manual commit
```

并且必须发生在 PostgreSQL Transaction 成功以后。

------

# 13. Redis 为什么同时有 fail-open 和 fail-closed

这是 WP0 很值得学习的一点。

Redis Cache：

```text
Redis down
    ↓
Cache miss / error
    ↓
直接调用真实 Retrieval
```

所以：

```text
fail-open
```

因为 Redis Cache：

> 只是性能优化，不是 Authority。

但 Rate Limiter：

```text
Redis down
```

如果直接放行：

```text
所有请求无限进入模型
```

可能导致资源耗尽。

因此最终：

```text
Rate Limiter outage
        ↓
503
```

即：

```text
fail-closed
```

所以：

> 同一个 Redis 故障，不能机械采用统一降级策略，要根据 Redis 在具体业务中的角色决定。

------

# 14. 为什么 Redis 不做分布式锁

原规划曾考虑：

```text
Distributed Lock
```

但 WP0 最终：

```text
REDIS_DISTRIBUTED_LOCK = NO
```

原因不是 Redis 做不了。

而是当前没有一个真正需要：

```text
跨实例强互斥
```

的明确业务临界区。

缓存击穿暂时通过：

```text
local single-flight
+
TTL jitter
```

处理。

如果为了简历硬加：

```text
Redlock
```

反而容易产生一个无法解释：

```text
谁需要锁？
为什么需要？
锁失效后如何防 stale owner？
```

的伪设计。

因此最终选择：

> Redis 能力要为了后端面试建设，但仍然要求它承担一个合理的业务责任。

------

# 15. 为什么 API / Publisher / Worker 拆三个进程

如果都塞在：

```text
FastAPI lifespan
```

里面：

```text
API
Publisher
Kafka Consumer
```

会产生：

```text
Uvicorn worker = 2
        ↓
Publisher = 2
Consumer = 2
```

这些数量变成 Web Server 的副作用。

同时：

```text
API crash
```

会把：

```text
Publisher
Worker
```

一起杀掉。

最终设计：

```text
localagent-api
outbox-publisher
evaluation-worker
```

它们：

```text
独立生命周期
独立 Connection Pool
独立 Shutdown
独立 Scaling
```

这也是以后 Docker/K8s 的基础。

------

# 16. 为什么 Agent Runtime 仍然只允许 1 个 Replica

当前：

```text
RunRegistry
ToolApprovalController
Execution Claim
```

依然是：

```text
process-local
```

如果部署：

```text
Pod A
Pod B
```

Run 在 A：

```text
run_id = R1
```

但下一次 Approval 请求被 Service LoadBalancer 分到 B：

```text
Pod B
    ↓
找不到 R1
```

所以直接：

```text
replicas = 3
```

不等于：

```text
distributed Agent Runtime
```

WP0 因此冻结：

```text
Agent Runtime API
replicas = 1
```

Publisher 和 Evaluation Worker 可以独立扩容。

这是 Stage6 的一个明确 Completion Boundary，而不是隐藏缺陷。

------

# 17. 为什么 Migration 不能在 API Startup 自动执行

如果 Kubernetes：

```text
replicas = 3
```

每个 Pod startup 都：

```text
alembic upgrade head
```

可能同时执行 Schema Migration。

同时 Migration：

```text
失败
```

也会与应用启动生命周期混在一起。

最终：

```text
Migration Owner
=
Explicit Deployment Command
/
Compose Init
/
Kubernetes Migration Job
```

而不是：

```text
FastAPI startup
```

Kubernetes rollout：

```text
Migration Job
    ↓ PASS
Deploy new application
```

Migration 失败：

```text
block rollout
```

------

# 18. 工程方法类问答

## Q1：为什么 PostgreSQL 要统一接管所有关系型数据，而不是 SQLite 和 PostgreSQL 共存？

因为 Stage6 后续需要跨 Job、Outbox、Dedup 等对象构建真实事务边界。如果同一个业务操作横跨 SQLite 和 PostgreSQL，就无法获得单数据库 ACID Transaction，只会制造新的分布式事务问题。

------

## Q2：为什么 Repository 不能自己 commit？

因为 Repository 只能看到自己的持久化操作，看不到完整业务事务。

一个 Job 创建动作可能同时需要：

```text
Job INSERT
+
Outbox INSERT
```

Transaction Owner 必须位于同时理解这两个动作的 Application Service。

------

## Q3：为什么 Outbox 能解决 DB + Kafka 双写问题？

因为它不再要求：

```text
数据库事务
+
Kafka
```

原子。

它把：

```text
Business Fact
+
Message Intent
```

放入同一个 PostgreSQL Transaction。

后续 Kafka 发送允许失败和重试。

------

## Q4：用了 Kafka idempotent producer，为什么还需要 Consumer Dedup？

Kafka Producer Idempotence 解决的是 Producer → Broker 某些重复写入问题。

它无法解决：

```text
Broker ack 成功
Publisher crash
published_at 未更新
```

导致应用再次发送相同业务 Event 的问题。

所以稳定的业务 `event_id` 和 Consumer Dedup 仍然需要。

------

## Q5：为什么 DB Commit 后才能 Commit Kafka Offset？

如果：

```text
offset commit
↓
DB transaction
```

然后 DB 失败：

Kafka 已经认为消息消费完成，消息可能永久丢失。

所以顺序必须：

```text
Business transaction commit
↓
Offset commit
```

代价是允许重复投递，再通过 Idempotency 消除重复副作用。

------

## Q6：Redis 为什么不能作为 Job Authority？

因为 Job 需要：

```text
transaction
constraint
durability
query
relation
outbox
```

Redis 在这个设计里承担：

```text
Cache
Rate Limit
```

而不是长期业务事实。

------

## Q7：为什么不能直接把 RunRegistry 放 Redis，然后支持多副本？

因为 RunRegistry 并不只是一个 `run_id -> state` 字典。

它涉及：

```text
Runtime Owner
Cancellation
Approval
Execution Claim
Connection / Stream Routing
Recovery
```

把一个 Dictionary 换成 Redis 不等于解决完整分布式 Ownership。

------

## Q8：为什么 Kafka Topic 不给每个 Run 建一个？

Topic 是基础设施级长期资源，不应该跟单个业务实例一一对应。

应该：

```text
Topic = event category
Partition Key = aggregate identity
```

所以：

```text
evaluation.jobs.v1
```

承载所有 Job。

------

## Q9：为什么用 `varchar + CHECK` 而不是 PostgreSQL Enum？

WP0 的理由是降低跨进程部署期间 Enum DDL 演进成本。

应用状态仍然通过：

```text
CHECK
```

保证合法范围。

------

## Q10：Connection Pool 应该属于谁？

每个进程的 Application Lifecycle。

因此：

```text
API        → own pool
Publisher  → own pool
Worker     → own pool
```

不能跨进程共享 Pool。

------

# 19. 30 秒面试总结

Stage6 的第一步我先把整个后端平台架构冻结了。关系型持久化统一从 SQLite 迁到 PostgreSQL，技术栈采用 SQLAlchemy Async、asyncpg 和 Alembic，事务由 Application Service 统一管理。异步后台任务采用 Evaluation Job 作为业务主链，Job 和 Outbox 在同一个 PostgreSQL Transaction 中提交，再由独立 Publisher 发 Kafka，Consumer 通过数据库唯一键做幂等，整体采用 At-least-once，而不是宣称端到端 Exactly-once。Redis 负责 RAG Cache 和分布式限流，API、Publisher、Worker 分成独立进程，最后通过 Docker Compose 和 Kubernetes 部署。

------

# 20. 2 分钟面试总结

我在补 LocalAgent 后端能力时，没有直接开始往项目里塞 Redis 和 Kafka，而是先做了一轮 Backend Architecture Decision。

首先我把关系型数据统一迁到 PostgreSQL，避免 SQLite 和 PostgreSQL 双 Authority。数据库层选择 SQLAlchemy 2.x Async + asyncpg + Alembic，Application Service 是 Transaction Owner，Repository 只负责数据访问，不允许自己 commit。

然后为了让 Kafka 有一个真实业务场景，我设计了 Durable Evaluation Job。创建 Job 时，`evaluation_jobs` 和 `outbox_events` 在同一个 PostgreSQL Transaction 中提交。独立的 Outbox Publisher 通过 `SELECT FOR UPDATE SKIP LOCKED` Claim 事件并发送 Kafka。

Kafka 整体采用 At-least-once，因为存在 Kafka 已经 ACK 但 Publisher 在更新 `published_at` 前崩溃的窗口，所以重复消息是允许的。Consumer 在 PostgreSQL 中通过 `(consumer_name, event_id)` 唯一约束做 Dedup，先提交 Result、Job 状态和 Dedup Transaction，再提交 Kafka Offset。这样即使 DB Commit 之后 Consumer 崩溃导致 Kafka Redelivery，也不会重复写业务结果。

Redis 不承担业务 Authority，只负责 Cache-Aside RAG Cache 和基于 Lua Token Bucket 的分布式 Rate Limiter。Cache Redis 故障时可以 bypass，Limiter 故障则 fail-closed。

部署上 API、Outbox Publisher 和 Evaluation Worker 是三个独立进程。因为当前 RunRegistry、Approval 和 Execution Claim 仍是 process-local，所以 Agent Runtime 暂时只支持一个 active replica，我没有因为用了 Kubernetes 就虚构已经支持 Agent Runtime 水平扩展。

------

# 21. 高频追问 + 简答

### Outbox 能做到 Exactly-once 吗？

不能。Outbox 通常提供 At-least-once Delivery，Kafka 成功但数据库 published 状态更新前崩溃仍然会造成重复，需要 Consumer Idempotency。

### 为什么不直接 Kafka Transaction？

Kafka Transaction 不能直接把任意 PostgreSQL Transaction、文件系统或外部 API 副作用纳入同一个原子事务。

### 为什么消费者去重要和业务写入同一个事务？

否则可能出现：

```text
Dedup 标记成功
业务更新失败
```

下一次消息会被误认为已经执行过。

### `SKIP LOCKED` 有什么作用？

多个 Publisher 并发扫描 Outbox 时，跳过已经被其它 Publisher 锁定的记录，实现数据库级并行 Claim。

### JWT 中已经有 roles，为什么 PostgreSQL 还有 user_roles？

JWT roles 是当前 Credential 的权限快照；PostgreSQL User/Role 是平台身份 Authority。

### Redis Cache 为什么不直接删除旧 Generation 的 Key？

Cache Key 带 Index Generation，新 Generation 自动生成不同 Key，旧 Key 等 TTL 自然过期，避免复杂的批量失效操作。

### Kafka 为什么要 Manual Commit？

需要确保业务数据库事务成功后才推进 Offset，从而避免消息已经提交 Offset 但业务操作失败导致消息丢失。

### 为什么不让 FastAPI 自己跑 Consumer？

Consumer 是独立长期 Worker，它的数量、生命周期和扩缩容不应该由 Uvicorn Worker 数量决定。

### 为什么 API Replica 只能是 1？

因为当前 Agent Runtime 的 RunRegistry、Approval、Execution Claim 仍然是进程内 Authority。

### 那 Kubernetes 有什么意义？

Kubernetes 仍然能够提供 Deployment、Service、Probe、Secret、资源限制、Rolling Update 和 Worker/Publisher 独立扩缩容；只是不能把这些能力错误等价成 Agent Runtime 已完成分布式 Ownership。

------

# 22. Bad Case / Failure Scenario

## Bad Case 1：DB 后直接发 Kafka

```text
INSERT Job
COMMIT

Kafka Publish
```

Kafka 失败后 Job 永远没人消费。

**解决：Transactional Outbox。**

------

## Bad Case 2：Kafka Offset 先 Commit

```text
commit offset
↓
write PostgreSQL
↓
DB failure
```

Kafka 不再投递这条消息，业务事实永久丢失。

**正确：DB Commit → Offset Commit。**

------

## Bad Case 3：Consumer Dedup 和 Result 分两个事务

```text
INSERT dedup
COMMIT

INSERT result
→ crash
```

重新收到消息：

```text
dedup exists
→ skip
```

Result 永远不存在。

**正确：Dedup + Business Mutation 同事务。**

------

## Bad Case 4：Rate Limiter Redis 挂了就无限放行

Redis 故障期间所有请求进入模型：

```text
traffic spike
→ model saturation
→ DB saturation
→ cascading failure
```

WP0 决定受保护 API：

```text
Redis limiter unavailable
→ 503
```

------

## Bad Case 5：Kubernetes replicas=3 就认为支持分布式 Runtime

Run 在 Pod A。

Approval 被负载均衡到 Pod B。

Pod B 没有 RunRegistry State。

结果：

```text
404 / invalid approval
```

所以当前必须：

```text
Agent Runtime active replica = 1
```

------

## Bad Case 6：Repository 自己 commit

JobRepository：

```text
insert job
commit
```

OutboxRepository：

```text
insert outbox
→ failure
```

直接重新制造双写问题。

------

# 23. Truth Boundary

WP0 当前真实完成：

```text
✅ PostgreSQL 技术栈决策
✅ Database Authority 决策
✅ Transaction Owner 决策
✅ Durable Evaluation Job 架构
✅ Transactional Outbox Contract
✅ Kafka Topic / Partition / Consumer / Offset Contract
✅ Redis Cache / Limiter Contract
✅ JWT / Principal / RBAC Contract
✅ API / Publisher / Worker 进程模型
✅ Docker Compose 架构
✅ Kubernetes Replica Boundary
✅ Prometheus / OpenTelemetry 目标架构
✅ Breaking Change Strategy
✅ WP1 Implementation Contract
```

当前没有真实完成：

```text
❌ PostgreSQL 接入
❌ SQLAlchemy models
❌ asyncpg Connection Pool
❌ Alembic Migration
❌ SQLite → PG migration
❌ JWT
❌ RBAC
❌ Redis
❌ Kafka
❌ Outbox Publisher
❌ Evaluation Worker
❌ Docker
❌ Kubernetes
❌ Prometheus
❌ 标准 OpenTelemetry
```

因此当前面试中：

> 可以讲“我为什么这样设计 Stage6”。

但暂时不能讲：

> “这些组件已经全部在 LocalAgent 上线运行”。

------

# 24. Completion Boundary

WP0 的完成标准不是代码上线。

而是：

```text
Architecture
Owner
Authority
Contract
Process Boundary
Dependency Graph
```

已经冻结。

最终结论：

```text
WP0_STATUS = COMPLETE

P0 = 0
BLOCKING_P1 = 0

ARCHITECTURE_REOPEN_REQUIRED = NO

WP1_READY = YES
CAN_ENTER_WP1 = YES
```

因此 WP1 实施 Agent 不应该重新讨论：

```text
用不用 PostgreSQL
用 asyncpg 还是其它 driver
用不用 SQLAlchemy
Outbox 跟谁一个事务
Kafka 用什么 client
谁拥有 Transaction
```

这些已经是 Frozen Architecture。

------

# 25. Known Limitation / ACCEPTED_P1

当前候选 Accepted Limitation：

### 1. Agent Runtime 单 Active Replica

```text
RunRegistry
Approval
Execution Claim
```

仍为 process-local。

Stage6 不解决整个 Agent Runtime Distributed Ownership。

------

### 2. Docker Compose 单 Kafka Broker

只用于：

```text
真实功能闭环
开发
面试 Demo
```

不宣称：

```text
Kafka High Availability
```

------

### 3. Stage6 不实现完整 IAM

只建设：

```text
JWT Verification
Principal
RBAC
Object Ownership
```

不建设：

```text
Password Login
Refresh Token
IAM Admin UI
```

------

### 4. External Evaluator Side Effect 不承诺 Exactly-once

数据库中的：

```text
Evaluation Result
```

可以做到幂等。

但如果 Evaluation Executor 调用外部不可幂等系统：

```text
External Side Effect
```

不属于 PostgreSQL Consumer Dedup 能保证的范围。

这些均被 WP0 列为候选 ACCEPTED_P1，而 Outbox 丢消息、Result 重复写、Principal 可伪造、Secret 泄漏则明确不能接受。

------

# 26. 本 WP 面试关键词

建议重点掌握：

```text
PostgreSQL

SQLAlchemy Async
asyncpg
Alembic

Connection Pool
Unit of Work
Repository Pattern
Transaction Boundary

Data Authority
Canonical Implementation

Transactional Outbox
Dual-write Consistency

SELECT FOR UPDATE
SKIP LOCKED
Lease
Claim

Kafka
Producer
Topic
Partition
Partition Key
Consumer Group
Offset
Manual Commit
DLQ
Rebalance

At-least-once
Exactly-once
Idempotent Consumer

Redis
Cache-Aside
TTL
TTL Jitter
Token Bucket
Lua Atomic Operation
Fail-open
Fail-closed

JWT
Principal
RBAC
Object-level Authorization

Prometheus
OpenTelemetry
W3C Trace Context

Docker Compose
Kubernetes
Readiness
Liveness
Rolling Update
Graceful Shutdown

Horizontal Scaling
Process-local State
Distributed Ownership
```

其中 WP0 最值得优先吃透的五个主题是：

```text
1. Transaction Owner 为什么在 Application Service

2. Transactional Outbox 为什么能解决 DB + Kafka 双写

3. At-least-once + Idempotent Consumer 的真实语义

4. Redis Cache fail-open 与 Rate Limiter fail-closed 为什么不同

5. Kubernetes 多副本为什么不能解决 process-local Runtime Ownership
```

这五个问题后面 WP1～WP8 基本都会再次出现，也是整个 Stage6 最核心的后端系统设计主线。