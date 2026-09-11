# Stage6-WP1 — PostgreSQL Persistence Foundation

## PostgreSQL 持久化基础学习 / 面试总结

------

# 1. 名词 / 概念速览

**PostgreSQL**：本 WP 替代 SQLite、成为 LocalAgent 关系型持久化唯一生产 Authority 的数据库。

**SQLAlchemy 2.x Async**：本项目 PostgreSQL 的异步 ORM / SQL Toolkit，上层负责模型映射和 SQL 构造。

**asyncpg**：SQLAlchemy 与 PostgreSQL 之间使用的异步 Python Driver。

**Alembic**：负责 PostgreSQL Schema Version 和显式 Migration 的工具，不在 FastAPI Startup 自动执行。

**异步数据库引擎（AsyncEngine）**：Application Scope 的 SQLAlchemy Engine，负责连接池和数据库生命周期。

**异步会话（AsyncSession）**：一次数据库操作或事务使用的独立 Session，不在并发任务之间共享。

**连接池（Connection Pool）**：复用数据库连接并限制数据库并发，本项目明确配置 pool size、overflow、timeout、recycle 和 pre-ping。

**事务拥有者（Transaction Owner）**：负责 BEGIN / COMMIT / ROLLBACK 的业务层 Owner，本项目是 Store / Application Service，而不是 Repository。

**Repository**：执行具体 SELECT / INSERT / UPDATE 的窄持久化接口，本项目禁止 Repository 自己 commit。

**数据库权威（Database Authority）**：某类持久化事实最终以哪个数据库为准；WP1 后 Memory、Journal、Snapshot、Checkpoint 都以 PostgreSQL 为准。

**数据库迁移（Database Migration）**：通过 Alembic 从空库构建或升级 Schema，而不是运行时偷偷改表。

**只读就绪检查（Read-only Schema Readiness）**：Startup 只检查数据库是否可达、Schema 是否存在、Alembic Revision 是否匹配，不执行 DDL。

**全文检索（Full Text Search, FTS）**：Memory Search 从 SQLite FTS5 迁移到 PostgreSQL `tsvector + GIN + websearch_to_tsquery + ts_rank`。

**GIN 索引（Generalized Inverted Index）**：PostgreSQL 常用于全文检索和 JSONB 的倒排索引结构。

**JSONB**：PostgreSQL 二进制 JSON 类型，本项目用于 Long-term / Project Semantic Memory 等没有 Digest Identity 的结构化 Payload。

**部分唯一索引（Partial Unique Index）**：只对满足 WHERE 条件的数据强制唯一，本项目用于 Terminal、Memory Exchange 等业务不变量。

**事务级咨询锁（Transaction-level Advisory Lock）**：本项目 Journal 使用 `pg_advisory_xact_lock` 按 `run_id` 串行化同一个 Run 的并发写入。

**Statement Timeout**：限制单条 SQL 的最大执行时间。

**Pool Acquire Timeout**：连接池没有可用连接时，最多等待多久。

**Lock Timeout**：数据库获取锁最多等待多久；当前实现已配置，但真实锁竞争测试尚未完成。

**Canonical JSON**：固定序列化格式；Runtime Journal 的 `safe_payload` 仍使用 Text 保存，以避免 JSONB 规范化改变 Digest Source。

------

# 2. 本 WP 真实完成了什么

WP1 最终已经完成：

```text
SQLite relational persistence
            ↓
PostgreSQL canonical persistence
```

以下四个领域全部迁移：

```text
Memory
Runtime Journal
Snapshot
Event Consumer Checkpoint
```

生产路径不存在：

```text
PostgreSQL failure
→ SQLite fallback
```

最终技术栈：

```text
PostgreSQL 16
      ↓
asyncpg
      ↓
SQLAlchemy 2.x Async
      ↓
AsyncEngine / AsyncSession
      ↓
Application Service / Store
```

同时建立：

```text
Alembic Migration
Connection Pool
Schema Readiness
Database Timeout
PostgreSQL FTS
JSONB
Database Constraints
SQL Injection Guard
Real PostgreSQL Integration Tests
```

Codex 最终确认生产 `server.py::lifespan()` 中 Memory、Journal、Snapshot、Checkpoint 都注入同一个 Application Scope `Database`。

------

# 3. 当前数据库架构与调用链

生产数据库生命周期：

```text
server.py::lifespan()
        ↓
DatabaseConfig
        ↓
Database
├─ AsyncEngine
├─ Connection Pool
└─ async_sessionmaker
        ↓
Read-only Schema Readiness
        ↓
PostgresMemoryManager
PostgresRunEventJournal
PostgresSnapshotStore
PostgresEventConsumptionCheckpointStore
```

关闭：

```text
Application Shutdown
        ↓
Database.close()
        ↓
AsyncEngine.dispose()
        ↓
Connection Pool 释放
```

Database 是：

```text
Engine Owner
Pool Owner
Session Factory Owner
```

但不是：

```text
Business Transaction Owner
```

------

# 4. 为什么从 SQLite 全面迁 PostgreSQL

原来 LocalAgent 使用多个 SQLite Store：

```text
Memory DB
Runtime Journal DB
Snapshot
Checkpoint
```

SQLite 本身并不是错误选择，之前也已经实现：

```text
BEGIN IMMEDIATE
WAL
UNIQUE
Transaction
Rollback
```

但 Stage6 的目标已经变成后端与分布式系统。

后续还需要：

```text
Auth
Evaluation Job
Transactional Outbox
Kafka Consumer Dedup
Worker
```

如果继续保留：

```text
SQLite Runtime
+
PostgreSQL Backend Job
```

将形成多个关系型 Authority。

之后想实现：

```text
Business State
+
Outbox Event
```

同事务提交就会很困难。

因此 WP0 冻结：

```text
All relational persistence
→ PostgreSQL
```

WP1 把这个决定真正落地。

------

# 5. 为什么不是简单“把 SQL 改成 PostgreSQL”

迁移数据库真正困难的是：

> 保持业务 Contract，而不是改 SQL 语法。

例如 SQLite Journal 原本使用：

```text
BEGIN IMMEDIATE
+
RLock
```

PostgreSQL 并没有机械复刻这套机制。

新的实现使用：

```text
pg_advisory_xact_lock(run_id)
+
PostgreSQL Transaction
+
Unique Constraints
```

但仍然保持：

```text
Journal-first
sequence monotonic
event_id uniqueness
duplicate idempotency
sequence conflict
terminal invariant
canonical digest
safe payload
```

Codex Review 最终确认这些 Journal Contract 均保持不变。

这体现一个很重要的工程原则：

> 数据库实现可以变化，但上层业务不变量不能因为换数据库而改变。

------

# 6. Transaction Owner 为什么不是 Repository

当前约定：

```text
Application Service / Store Boundary
          ↓
database.transaction()
          ↓
Repository
```

Repository 只能：

```text
SELECT
INSERT
UPDATE
DELETE
flush
```

不能：

```text
commit()
rollback()
begin()
create Session
```

Codex Review 已确认 `core/persistence/repositories/runtime.py` 没有隐藏这些事务操作。

原因是 Repository 不知道完整业务操作。

例如：

```text
写 Message A
写 Message B
更新 Exchange COMMITTED
```

如果 Repository 各自提交：

```text
Message A COMMIT
        ↓
Message B COMMIT
        ↓
Exchange 更新失败
```

业务状态就不完整。

因此必须由更高层统一拥有事务。

------

# 7. Memory Atomic Transaction

Memory Migration 中一个关键 Contract 是：

```text
append_exchange_atomic()
```

完整 Exchange：

```text
BEGIN

Create Exchange(PENDING)

Insert User Message

Insert Assistant Message

Update Exchange(COMMITTED)

COMMIT
```

其中任一步失败：

```text
ROLLBACK ALL
```

只有：

```text
COMMITTED
```

Exchange 中的消息才能被：

```text
history
search
count
```

看到。

Codex Review 正好发现了一个 Bug：

```text
count_messages()
```

原来没有过滤：

```text
PENDING
```

导致未提交 Exchange 虽然 History 看不到，却可能影响 Summary Threshold。

Review 直接把它修成和 History / FTS 一致的 `COMMITTED` Visibility Contract，并通过真实 PG 测试。

这是一个很好的数据库一致性面试案例：

> “原子写入”不仅指事务成功或失败，还要求所有读取投影使用一致的可见性规则。

------

# 8. SQLite FTS5 怎么迁到 PostgreSQL

原来：

```text
SQLite FTS5
+
external-content table
+
triggers
```

迁移后：

```text
PostgreSQL

generated tsvector
        ↓
GIN Index
        ↓
websearch_to_tsquery
        ↓
ts_rank
```

所以：

```text
Memory Query
    ↓
FTS Query
    ↓
GIN Index
    ↓
Rank
```

不是简单：

```sql
WHERE content ILIKE '%keyword%'
```

Codex Review 明确确认 PostgreSQL FTS 是生产主实现，而不是 Schema 建了 GIN 最后查询仍全部走 ILIKE。

------

# 9. 为什么 Journal safe_payload 不用 JSONB

这是 WP1 一个很值得面试讲的细节。

一般看到 PostgreSQL：

```text
JSON data
→ JSONB
```

似乎很自然。

但 Runtime Journal 的：

```text
safe_payload
```

参与：

```text
canonical JSON
→ SHA-256
→ event_digest
```

JSONB 可能对：

```text
key
number
representation
```

进行自己的规范化。

因此如果：

```text
写入前 digest source
≠
读取后的 representation
```

可能破坏历史 Evidence Identity。

所以最终：

```text
Journal safe_payload → TEXT
```

保持 canonical JSON 原文。

而：

```text
long_term_memory payload
project_semantic_memory payload
```

不存在同样的 Digest Identity 约束，因此使用：

```text
JSONB
```

这体现：

> 数据类型选择首先服从业务 Contract，而不是追求“PostgreSQL 最佳实践形式”。

------

# 10. PostgreSQL Journal 并发是怎么解决的

同一个 Run 可能同时产生事件。

要求：

```text
sequence
```

必须严格单调。

WP1 使用：

```text
pg_advisory_xact_lock(hash(run_id))
```

事务级锁。

流程：

```text
BEGIN

Advisory Lock(run_id)

Read Current Journal State

Validate:
event_id
sequence
terminal

INSERT event

COMMIT
```

同一个 Run：

```text
Run A Event 1
Run A Event 2
```

会串行决策。

不同 Run：

```text
Run A
Run B
```

不会因为一个全局锁彼此阻塞。

最终数据库还有：

```text
PRIMARY KEY(run_id, sequence)
UNIQUE(event_id)
Partial Unique RUN_COMPLETED
```

作为最后一层 Authority。

因此形成：

```text
Application decision
+
transaction-level serialization
+
database constraint
```

三层保护。

------

# 11. Advisory Lock 和普通 Row Lock 有什么区别

普通：

```sql
SELECT ... FOR UPDATE
```

需要：

> 已经有一行可以锁。

但 Journal 在：

```text
第一个 Event
```

到来时，这个 Run 可能还没有任何数据库行。

这时：

```text
Advisory Lock(run_id)
```

可以直接以业务 Identity 创建逻辑锁。

而且：

```text
pg_advisory_xact_lock
```

随 Transaction 自动释放。

不会要求业务代码手动 Unlock。

------

# 12. 数据库约束为什么不能只写 Python Validation

例如 Terminal：

```text
一个 Run 最多一个 RUN_COMPLETED
```

如果只写：

```python
if terminal_exists:
    reject()
```

两个并发 Transaction 都可能：

```text
read → no terminal
```

然后同时：

```text
insert RUN_COMPLETED
```

所以最终还需要数据库：

```text
Partial Unique Index
```

保证：

```text
最多一条 RUN_COMPLETED
```

Application Validation 提供：

```text
友好业务错误
```

Database Constraint 提供：

```text
最终一致性保护
```

这两个不是互相替代关系。

------

# 13. Connection Pool 是怎么设计的

当前数据库 Pool 配置包括：

```text
pool_size = 5

max_overflow = 5

pool_timeout = 5s

pool_recycle = 1800s

pool_pre_ping = true
```

还有：

```text
connect timeout
statement timeout
lock timeout
idle_in_transaction timeout
```

WP1 特别强调：

```text
Connection Pool Size
≠
Worker Concurrency
```

例如：

```text
20 async requests
```

不代表：

```text
一定要 20 database connections
```

Async Task 等待 Pool 本身就是背压的一部分。

------

# 14. Pool Exhaustion 是什么

假设：

```text
pool_size = 1
max_overflow = 0
```

Connection A：

```text
被 Transaction 1 占用
```

Transaction 2：

```text
请求 connection
↓
没有连接
↓
等待 pool_timeout
↓
DATABASE_POOL_EXHAUSTED
```

不能：

```text
无限等待
```

也不能把裸：

```text
SQLAlchemy TimeoutError
DSN
password
```

返回客户端。

WP1 已经使用真实 PostgreSQL 对 Pool Exhaustion 做过测试，并由 Codex Review 确认。

------

# 15. Statement Timeout 是什么

它控制的是：

> 一条 SQL 最长允许执行多久。

例如：

```sql
SELECT pg_sleep(...)
```

超过：

```text
statement_timeout
```

PostgreSQL 会终止 Statement。

系统需要保证：

```text
Statement Timeout
      ↓
Transaction Rollback
      ↓
Connection 恢复可用
      ↓
Return To Pool
```

不能因为一次 Timeout：

```text
把坏 Transaction 状态的 Connection
重新交给下一个 Request
```

WP1 的真实 PostgreSQL 测试已经覆盖：

```text
timeout
rollback
connection reusable
```

------

# 16. Pool Timeout、Statement Timeout、Lock Timeout 区别

可以这样记：

```text
Pool Timeout
=
我连数据库 Connection 都还没拿到
Statement Timeout
=
Connection 已经拿到了
SQL 执行太久
Lock Timeout
=
SQL 想执行
但是一直在等别人释放数据库锁
```

还有：

```text
Idle In Transaction Timeout
=
Transaction 已经打开
但客户端长时间什么都不做
```

四种 Timeout 解决的是四种不同资源等待问题。

------

# 17. 为什么数据库不能在 FastAPI Startup 自动 Migration

WP1 的 Startup：

```text
Database Connect
        ↓
Read-only Readiness
        ↓
Check Schema
Check Alembic Head
```

不会：

```text
alembic upgrade head
```

原因是未来部署可能有：

```text
Pod A
Pod B
Pod C
```

如果三个 Pod 同时 Startup Migration：

```text
三份 Schema Writer
```

会导致 Migration Ownership 不清楚。

所以：

```text
Alembic Migration
```

以后由：

```text
explicit deployment command
Docker Compose migration
Kubernetes Migration Job
```

执行。

API 只负责：

```text
Schema ready?
YES → Start
NO  → Fail Closed
```

Codex Review 已确认这一边界。

------

# 18. 为什么全部 PostgreSQL I/O 要异步

LocalAgent 本身是：

```text
FastAPI
+
AsyncIO
```

旧代码曾出现：

```text
async HTTP
    ↓
sync SQLite
```

同步数据库 I/O 可能直接阻塞：

```text
Event Loop
```

例如一个 SQLite Lock：

```text
wait 5s
```

可能不是：

> 一个请求慢 5 秒。

而是：

> Event Loop 中其他 Coroutine 也被拖慢。

WP1 后 steady-state PostgreSQL：

```text
AsyncSession
    ↓
SQLAlchemy Async
    ↓
asyncpg
```

均为 Awaitable。

Codex Review 已确认生产不存在：

```text
async HTTP → sync SQLite
```

路径。

------

# 19. AsyncSession 为什么不能跨并发 Task 共享

AsyncSession 本身：

> 表示一个数据库工作单元和事务状态。

如果：

```text
Task A
Task B
```

同时共享：

```text
Session S
```

两个 Task 的：

```text
Transaction State
Flush State
Rollback State
Connection State
```

会互相影响。

因此当前规则：

```text
each concurrent operation
→ independent AsyncSession
```

而：

```text
AsyncEngine / Session Factory
```

可以是 Application Scope。

------

# 20. Repository Pattern 在本项目里为什么比较轻

WP1 没有建设：

```text
GenericBaseRepository<T>
CRUD Framework
DAO Framework
```

而是：

```text
narrow repositories
```

原因是数据访问行为差异很大。

例如：

```text
Journal
```

需要：

```text
Advisory Lock
Sequence
Terminal Constraint
```

Memory：

```text
FTS
JSONB
Visibility
Atomic Exchange
```

如果统一成：

```text
repository.save(entity)
```

反而隐藏真正重要的数据库语义。

所以这里追求的是：

> Repository 隔离 Persistence Logic，而不是抽象掉 SQL 本身。

------

# 21. 工程方法类问答

## Q1：为什么从 SQLite 换 PostgreSQL？

不是因为 SQLite 不能做事务，而是 Stage6 后续需要更完整的并发数据库能力、连接池、异步访问、Outbox、Kafka Consumer Dedup 和多进程 Worker。统一 PostgreSQL 还能避免 SQLite/PG 双 Authority。

------

## Q2：为什么用 SQLAlchemy，而不是直接 asyncpg？

SQLAlchemy Async 能统一 Engine、Pool、Session、Transaction 和 Model Mapping，同时复杂场景仍能使用 Core。直接 asyncpg 也能实现，但会自行承担更多 Mapping 和 Persistence Infrastructure 工作。

------

## Q3：为什么 Repository 不允许 commit？

因为完整业务事务可能跨多个 Repository，只有 Application Service 知道一个业务操作什么时候真正完成。

------

## Q4：为什么需要数据库 Constraint，Application 校验还不够吗？

Application 的 read-check-write 在并发下存在竞态，数据库 Constraint 才是最终 Authority。

------

## Q5：为什么 Journal 用 Advisory Lock？

因为需要按 `run_id` 串行化 Journal 决策，而且新 Run 第一个 Event 到来时可能还没有可供 `FOR UPDATE` 锁定的数据行。

------

## Q6：Advisory Lock 会不会把整个数据库锁住？

不会。本项目 Lock Key 根据 `run_id` 生成，所以只串行化同一个 Run，不同 Run 可以并发。

------

## Q7：为什么 Memory Search 不直接用 ILIKE？

ILIKE 对简单小数据可以工作，但无法提供真正的全文检索索引与 Ranking。当前使用 PostgreSQL `tsvector + GIN + ts_rank`。

------

## Q8：JSON 为什么有的用 TEXT，有的用 JSONB？

如果 JSON Representation 本身参与 Digest Identity，就保留 Canonical JSON Text；如果主要用于结构查询和索引，则使用 JSONB。

------

## Q9：Migration 为什么不能 Startup 自动跑？

Migration 是 Schema Write Operation，需要独立部署 Owner；API Startup 只应该判断当前 Schema 能否运行。

------

## Q10：Connection Pool 越大越好吗？

不是。Pool 太大可能把数据库 Connection、Memory、Lock 和 CPU 压力放大。Pool Size 应根据 DB Capacity、进程数量和业务并发一起设计。

------

## Q11：asyncpg 已异步，为什么还需要 Pool？

异步解决的是等待期间不阻塞线程，不代表数据库 Connection 建立没有成本，也不代表数据库允许无限 Connection。

------

## Q12：数据库 Timeout 为什么需要分层？

因为获取连接、获取锁、执行 SQL、Transaction Idle 是不同 Failure Mode，需要不同的 Timeout 和错误语义。

------

# 22. 30 秒面试回答

我在 LocalAgent 的后端改造里把原来 Memory、Runtime Journal、Snapshot 和 Checkpoint 的 SQLite 持久化统一迁到了 PostgreSQL，数据库栈是 SQLAlchemy 2.x Async + asyncpg + Alembic。Engine 和连接池是 Application Scope，每个并发操作使用独立 AsyncSession，事务由 Application Service 或 Store 边界统一管理，Repository 不允许自己 commit。

迁移过程中没有机械复制 SQLite 锁逻辑，比如 Journal 改成了按 run_id 的 PostgreSQL transaction advisory lock，同时用 PK、Unique 和 Partial Unique Index 保证 Sequence、Event ID 和 Terminal 不变量。Memory Search 也从 FTS5 改成 PostgreSQL tsvector + GIN。最终所有生产关系型数据都以 PostgreSQL 为 Authority，没有 SQLite fallback。

------

# 23. 2 分钟面试回答

LocalAgent 最开始主要使用 SQLite，随着后端和分布式能力增加，我把 Memory、Runtime Journal、Snapshot 和 Consumer Checkpoint 全部迁到了 PostgreSQL。

数据库层选择 SQLAlchemy 2.x Async + asyncpg，Application Lifecycle 管理 AsyncEngine 和 Connection Pool，每个并发操作独立 AsyncSession。事务 Owner 放在 Application Service 或具体 Store 的业务边界，Repository 只负责 SQL，不允许自己 commit，这样后面做 Evaluation Job 和 Transactional Outbox 时可以保证多个 Repository 操作处于同一个 Transaction。

迁移时比较重要的一点是没有直接复制 SQLite 实现。例如 Runtime Journal 原来依赖 BEGIN IMMEDIATE 和本地锁，迁到 PostgreSQL 后，我使用 transaction-level advisory lock 按 run_id 串行化同一个 Run 的并发写，同时用 `(run_id, sequence)` 主键、`event_id` Unique 和 RUN_COMPLETED Partial Unique Index 作为数据库最终约束，保持原来的 Journal-first、Sequence 和 Terminal Contract。

Memory 方面，SQLite FTS5 迁成 PostgreSQL generated tsvector + GIN Index + websearch_to_tsquery + ts_rank；Long-term Memory 使用 JSONB，但 Journal safe payload 仍然保存 Canonical JSON Text，因为它参与 SHA-256 Digest Identity，不能让 JSONB Representation 改变历史证据。

另外我还实现了真实 Connection Pool Exhaustion 和 Statement Timeout 测试，确保 Pool Timeout 能返回 Typed Failure，Statement Timeout 后事务会 Rollback，而且 Connection 可以安全复用。Migration 使用 Alembic，但 FastAPI Startup 只做 Read-only Schema Readiness，不自动执行 Migration。

------

# 24. 高频追问 + 简答

### SQLite 有事务，为什么非得迁 PG？

SQLite 有事务，但 Stage6 后续需要连接池、多进程 Worker、Outbox、Kafka Consumer Dedup 和更强的并发数据库能力；统一 PG 还避免双 Authority。

### 为什么不使用 ORM 自动 commit？

因为自动 commit 会隐藏真正的业务事务边界，不适合 Job + Outbox 这类多表原子操作。

### Advisory Lock 是悲观锁吗？

它属于 PostgreSQL Application-defined Lock，可以用于悲观串行化某个业务 Identity；但它不是某张表具体 Row 的锁。

### 为什么还需要数据库 Unique Constraint？

因为 Advisory Lock 主要保护同 Run 竞争，而数据库 Constraint 仍是面对竞态、跨 Run Event ID 冲突等情况的最终 Authority。

### FTS 的 GIN 有什么作用？

GIN 是倒排索引，可以按 Token 快速找到匹配文档，而不是逐行扫描全文。

### JSONB 比 TEXT 好在哪里？

JSONB 更适合字段查询、索引和结构化条件，但如果原始序列化本身参与 Digest，则 TEXT 更安全。

### Connection Pool Exhausted 应该怎么办？

有界等待，超过 Pool Timeout 返回安全的 Typed 503，而不是无限排队或不断创建 Connection。

### Statement Timeout 后 Connection 还能直接复用吗？

要先确保 Transaction 已 Rollback，Connection 状态恢复正常后才能重新进入 Pool。

### `pool_size=5` 是不是只能并发 5 个请求？

不是。数据库 Connection 数和 HTTP Coroutine 并发数不是同一个概念，Coroutine 可以等待 Pool。

### Alembic 为什么要从空库测试？

因为要证明 Migration 本身能够独立构建完整 Schema，而不是依赖开发机已经存在的历史数据库状态。

------

# 25. Bad Case / Failure Scenario

## Bad Case 1：Repository 自己 Commit

```text
Service
 ↓
Repository A commit
 ↓
Repository B failure
```

结果：

```text
partial business state
```

正确：

```text
Service owns transaction
A + B
→ one commit
```

------

## Bad Case 2：所有 Request 共用 AsyncSession

Task A Rollback：

```text
Shared Session
```

可能影响 Task B 的事务状态。

正确：

```text
Engine shared
Session per operation
```

------

## Bad Case 3：只在 Python 检查 Terminal

两个事务：

```text
T1 read no terminal
T2 read no terminal

T1 insert terminal
T2 insert terminal
```

如果没有 DB Constraint：

```text
两个 terminal
```

正确：

```text
Application Check
+
Database Unique Constraint
```

------

## Bad Case 4：JSONB 存 Journal Canonical Payload

如果读取出来的 JSON Representation 与写入 Digest Source 不完全一致：

```text
historical digest mismatch
```

正确：

```text
Journal canonical payload → TEXT
```

------

## Bad Case 5：FastAPI Startup 自动 Alembic Upgrade

多个实例同时启动：

```text
Pod A migration
Pod B migration
Pod C migration
```

Schema Writer Owner 不清。

正确：

```text
Deployment Migration Owner
→ Schema ready
→ API startup
```

------

## Bad Case 6：Statement Timeout 后不 Rollback

SQL Timeout：

```text
Transaction aborted
```

如果 Connection 直接返回 Pool：

下一个用户拿到：

```text
aborted transaction
```

正确：

```text
Timeout
→ Rollback
→ Verify reusable
→ Pool
```

------

# 26. Truth Boundary

当前真实已实现：

```text
✅ PostgreSQL 16
✅ SQLAlchemy 2.x Async
✅ asyncpg
✅ AsyncEngine
✅ AsyncSession
✅ Connection Pool
✅ Alembic
✅ Read-only Schema Readiness

✅ PostgreSQL Memory
✅ PostgreSQL Runtime Journal
✅ PostgreSQL Snapshot
✅ PostgreSQL Checkpoint

✅ PostgreSQL Full Text Search
✅ tsvector
✅ GIN
✅ JSONB
✅ Partial Unique Index

✅ Journal Advisory Lock
✅ Journal DB Constraints

✅ Pool Exhaustion Test
✅ Statement Timeout Test

✅ SQL Injection Guard
✅ Recovery Async Compatibility

✅ Production SQLite Fallback Removed
```

Codex Review 最终确认这些边界全部成立。

当前尚未实现：

```text
❌ JWT / RBAC
❌ Redis
❌ Evaluation Job
❌ Transactional Outbox
❌ Kafka
❌ Docker Compose
❌ Kubernetes
❌ Prometheus / Standard OTel
```

它们属于后续 WP。

------

# 27. Completion Boundary

WP1 最终状态：

```text
WP1_REVIEW_STATUS = PASS

P0 = 0
BLOCKING_P1 = 0

POSTGRESQL_CANONICAL_AUTHORITY_CONFIRMED = YES

SQLITE_PRODUCTION_RELATIONAL_PATH_CONFIRMED_NONE = YES

CAN_CLOSE_WP1 = YES
CAN_ENTER_WP2 = YES
```

Review 过程中：

```text
BUGS_FOUND = 2
BUGS_FIXED = 2
```

因此：

> Review 发现 Bug 不等于 WP Fail。

最终判断看的是：

```text
修复后的 Canonical 工作树
```

而不是：

```text
审核过程中是否曾发现问题
```

这也成为之后 Stage6 的默认 Review 流程。

------

# 28. Known Limitation / ACCEPTED_P1

WP1 最终接受三个非阻断限制。

## 1. Lock Timeout 没有真实竞争测试

配置已有：

```text
lock_timeout
```

但：

```text
LOCK_TIMEOUT_TESTED = NO
```

没有构造两个真实 Transaction 抢锁的测试。

不影响当前主链，因此 Accepted。

------

## 2. Deadline 尚未传播到所有 DB Operation

当前已经有：

```text
RunFinalMemoryWriter
→ remaining budget
→ DB statement timeout
```

但不是：

```text
Every HTTP / Runtime DB Operation
```

都完整传递 Deadline。

所以当前状态：

```text
PARTIALLY_SUPPORTED
```

不能对外讲成全链 Deadline Propagation。

------

## 3. 没有自动 SQLite → PostgreSQL 历史数据导入

这是 WP0 明确排除的 Scope。

生产运行时已经：

```text
PostgreSQL only
```

但旧 SQLite 用户历史文件不会自动转换。

这不影响新 Canonical System。

Codex Review 确认这三个限制均不破坏 PostgreSQL 主链。

------

# 29. 本 WP 面试关键词

重点：

```text
PostgreSQL
SQLAlchemy 2.x
AsyncEngine
AsyncSession
asyncpg
Alembic

Connection Pool
pool_size
max_overflow
pool_timeout
pool_pre_ping

Transaction Boundary
Transaction Owner
Repository Pattern
Unit of Work

Primary Key
Unique Constraint
Partial Unique Index
GIN Index
JSONB

PostgreSQL Full Text Search
tsvector
websearch_to_tsquery
ts_rank

Advisory Lock
pg_advisory_xact_lock

Concurrency
Race Condition
Database Constraint

Statement Timeout
Lock Timeout
Pool Exhaustion
Transaction Rollback

Schema Migration
Schema Readiness

Async Database
Event Loop Blocking

Data Authority
Breaking Change
Canonical Persistence
```

------

# 30. 本 WP 最值得掌握的 7 个问题

如果时间有限，优先吃透：

```text
1. Transaction 为什么应该由 Service 而不是 Repository 拥有？

2. Application Validation 为什么不能替代 Database Constraint？

3. Journal 为什么使用 PostgreSQL Advisory Lock？

4. 为什么 safe_payload 用 TEXT，而 Memory Payload 用 JSONB？

5. Connection Pool、HTTP 并发、Worker Concurrency 有什么区别？

6. Pool Timeout、Statement Timeout、Lock Timeout 分别解决什么问题？

7. 为什么 Migration 和 Application Startup 必须分离？
```

这七个问题已经不只是 LocalAgent 特有问题，基本都是 Python 后端 / 数据库工程面试可以直接复用的知识。