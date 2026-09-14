当前是 **GPT-5.6 Sol**。

下面把 **Stage6 主线 WP0～WP9 + Stage6 Supplement WP10～WP12** 一起做成完整的学习 / 面试总结。两部分我会明确区分：**WP9 是原 Stage6 Distributed Backend Final Gate；WP10～12 是主线关闭后，为面试补强的三个 Supplement WP。**

推荐文档名：

```
docs/interview/stage6_overall_backend_security_context_sandbox.md
```

------

# 1. Stage6 到底解决了什么问题

Stage5 结束时，你已经有一个功能很强的 Agent Runtime：

```text
Agent Runtime
RAG
Memory
Tool / MCP
HITL
Multi-Agent
Evaluation
```

但它更偏向：

> **单机 Agent Runtime / Agent Harness。**

Stage6 做的事情，是把它向真正的 **AI Agent 后端平台**推进：

```text
Stage5 Agent Runtime
        ↓
PostgreSQL 权威持久化
        ↓
认证 / 权限 / Ownership
        ↓
Redis Cache / Rate Limit
        ↓
Durable Job + Transactional Outbox
        ↓
Kafka Reliable Messaging
        ↓
Prometheus / OpenTelemetry
        ↓
Docker Compose
        ↓
Kubernetes
```

主线最终全部 PASS：

```text
WP0 Architecture       PASS
WP1 PostgreSQL         PASS
WP2 Auth / API         PASS
WP3 Redis              PASS
WP4 Job / Outbox       PASS
WP5 Kafka              PASS
WP6 Observability      PASS
WP7 Docker Compose     PASS
WP8 Kubernetes         PASS
WP9 Final Gate         PASS
```

最终：

```ini
STAGE6_FINAL_GATE = PASS
P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 4
ARCHITECTURE_REOPEN_REQUIRED = NO
STAGE6_CAN_CLOSE = YES
```



随后又补：

```text
WP10 Agent Security / Prompt Injection       PASS
WP11 Context Engineering / LLM Gateway       PASS
WP12 Sandbox / Isolated Tool Execution       PASS
```

所以完整 Stage6 的意义可以概括成：

> **Stage5 解决 Agent 怎么运行，Stage6 解决 Agent 怎么作为一个可靠、安全、可部署、可观测的后端系统运行。**

------

# 2. Stage6 最终整体架构

完整架构可以这样理解：

```text
                         Client
                           │
                           ▼
                  FastAPI / Authentication
                           │
                      Principal / RBAC
                           │
                           ▼
                    Agent Runtime
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       Memory             RAG           Tool / MCP
          │                │                │
          └───────── Context Engineering ───┘
                           │
                           ▼
                   Model Invocation
                           │
                           ▼
                    Tool Intent
                           │
                     Typed Validation
                           │
                           ▼
                   Tool Governance
                           │
                    HITL if required
                           │
                           ▼
               Execution / Sandbox
                           │
                           ▼
                       Result
```

后台基础设施是另一条链：

```text
HTTP
 │
 ▼
PostgreSQL
 ├─ Memory
 ├─ Journal
 ├─ Snapshot / Checkpoint
 ├─ User / Role / Ownership
 ├─ Evaluation Job
 ├─ Result
 ├─ Outbox
 ├─ Consumer Dedup
 └─ Lease / Fencing
        │
        ▼
Transactional Outbox
        │
        ▼
Outbox Publisher
        │
        ▼
Kafka
        │
        ▼
Evaluation Worker
        │
        ▼
PostgreSQL
```

Redis 不承担业务 Durable Authority，而是：

```text
Redis
├─ RAG Cache
└─ Principal Rate Limiter
```

这套 Authority 是 Stage6 很重要的核心。最终 Gate 明确冻结：PostgreSQL 拥有持久业务事实，Kafka 拥有消息 Delivery / Offset，Redis 不是 Durable Authority。

------

# 3. WP0 — Backend Architecture

WP0 最重要的不是写代码，而是把整个 Stage6 的 Owner 冻结下来。

核心技术决策：

```text
PostgreSQL
SQLAlchemy 2 Async
asyncpg
Alembic

Redis
Kafka

API
Publisher
Worker
三个独立进程
```

PostgreSQL 成为：

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

的权威数据源。

最重要的数据库 Owner 原则：

```text
HTTP Route
→ DTO / Auth / Projection

Application Service
→ Transaction Owner

Repository
→ SQL / persistence operation
→ 不 commit
→ 不 rollback
→ 不自己创建 Session
```

这就是典型的工作单元（Unit of Work）设计。

### 面试核心

问：

> 为什么 Repository 不应该自己 commit？

答：

> 因为一个业务事务可能横跨多个 Repository。如果各 Repository 自己提交，就无法保证 Job、Outbox 等多个业务事实原子提交，所以 Transaction Owner 必须在 Application Service。

------

# 4. WP1 — PostgreSQL Canonical Persistence

这一 WP 把原来的 SQLite Production Authority 真正替换成 PostgreSQL。

核心：

```text
AsyncEngine
AsyncSession
asyncpg
Alembic
```

新的 Production Path 中：

```text
Memory
Journal
Snapshot
Checkpoint
```

都由 PostgreSQL 管理，SQLite 不再作为 Production Fallback。

非常重要的一点：

> Migration 不是 API Startup 的责任。

而是：

```text
Deployment command
Docker Compose migrate
Kubernetes Migration Job
```

拥有 Migration。

这避免多个 API 实例启动时争抢 Schema Migration。

### 面试核心

**为什么数据库迁移不能放在 API startup？**

因为多实例环境可能：

```text
API-1 startup
API-2 startup
API-3 startup
```

同时执行 Migration，产生竞争和不可控部署状态。

所以 Schema Migration 必须是独立 Deployment Step。

------

# 5. WP2 — Authentication / Authorization / Ownership

这里真正构建了 Human Identity Boundary。

认证链：

```text
Authorization: Bearer
        ↓
EdDSA JWT Verification
        ↓
PostgreSQL User / Role
        ↓
Frozen Principal
        ↓
Authorization / Ownership
```

JWT 中：

```text
iss
aud
sub
roles
jti
iat
nbf
exp
```

都要校验，而且 Token Role 不能超出 DB 当前角色，客户端不能通过自己伪造 Role 升级到 ADMIN。

最关键的设计：

> **Principal 必须来自服务器验证，而不是 Request Body。**

所以：

```text
actor_id
user_id
owner_id
```

不能成为身份 Authority。

### 一句话

> Authentication 解决“你是谁”，Authorization 解决“你能操作什么”，Object Ownership 解决“这个对象是不是你的”。

------

# 6. WP3 — Redis Cache & Traffic Governance

Redis 在 Stage6 中故意**没有**做万能中间件。

它只承担两个明确职责。

## RAG Cache

使用 Cache-Aside：

```text
Request
   ↓
Redis Cache
 ├─ HIT → cached projection
 └─ MISS / Redis failure
          ↓
      Original Retrieval
```

Redis 删除全部 Key，也不应该影响 Retrieval 正确性。

这就是：

> **Cache 不是 Authority。**

真实实现保存的是安全 Retrieval Projection，而不是 Runtime State 或整个 Retrieval Object。

Cache 故障：

```text
Fail Open
```

继续走 Origin Retrieval。

## Rate Limiter

Principal 维度 Token Bucket：

```text
Principal
   ↓
Redis Lua
   ↓
atomic read → decide → update
```

Limiter 故障：

```text
Fail Closed → 503
```

WP0 还明确：

```text
REDIS_DISTRIBUTED_LOCK = NO
```



这点以后写简历一定不要写 Redis 分布式锁。

------

# 7. WP4 — Durable Job + Transactional Outbox

这是 Stage6 最重要的分布式系统 WP 之一。

Job 生命周期：

```text
QUEUED
  ↓
RUNNING
  ↓
SUCCEEDED
FAILED
CANCELLED
```

真正关键的是事务发件箱（Transactional Outbox）。

错误设计：

```text
BEGIN
INSERT job
COMMIT

Kafka produce
```

问题：

```text
DB commit成功
Kafka发送失败
→ Job存在，但消息丢了
```

反过来也有：

```text
Kafka成功
DB commit失败
→ Consumer看到不存在的Job
```

所以使用：

```text
BEGIN PostgreSQL Transaction

INSERT EvaluationJob
INSERT OutboxEvent

COMMIT
```

然后独立 Publisher：

```text
SELECT ... FOR UPDATE SKIP LOCKED
        ↓
Lease / Claim
        ↓
Publish Kafka
        ↓
mark published
```

WP4 已真实证明 Job + Outbox Atomicity、Claim / Lease / Fencing 等。

------

# 8. WP5 — Kafka Reliable Messaging

Kafka 的最大知识点不是“会发消息”。

而是：

> **什么时候才能提交 Offset？**

当前链：

```text
Kafka Message
       ↓
Worker
       ↓
PostgreSQL Transaction
 ├─ Dedup
 ├─ Claim / Lease
 ├─ Business Result
 └─ Commit
       ↓
Kafka Manual Offset Commit
```

顺序一定是：

```text
DB Commit
BEFORE
Kafka Offset Commit
```

Producer：

```text
enable.idempotence=true
acks=all
```

但最终仍然明确：

```text
At-Least-Once
```

而不是 Exactly-Once。

原因是存在经典窗口：

```text
Kafka ACK
↓
Publisher crash
↓
PostgreSQL 尚未 mark published
```

恢复后同一个 Event 可能再次发送。

因此：

> Producer Idempotence ≠ End-to-End Exactly-Once。

Consumer 使用 PostgreSQL Dedup 消化重复 Delivery。

------

# 9. 最重要的一道分布式系统题：Exactly-Once

Stage6 最应该记住：

```text
Kafka At-Least-Once
+
PostgreSQL Consumer Dedup
+
Lease / Fencing
+
Idempotent Finalization
```

实现的是：

> **最终业务效果接近 Exactly-Once 的幂等语义。**

但不能声称：

> **Kafka + PostgreSQL End-to-End Exactly-Once。**

最终 Gate 明确禁止这个 Claim。

这是面试中比“我用了 Kafka”高级得多的点。

------

# 10. WP6 — Observability & Reliability

这一 WP 把原有 Runtime Observability 扩成真正 Backend Observability。

用了：

```text
Prometheus
OpenTelemetry
W3C Trace Context
```

每个 API / Publisher / Worker 进程各自拥有一个 ObservabilityService，而不是 Per Request 创建 Provider。

指标覆盖：

```text
HTTP
Redis
Job
Outbox
Kafka Producer
Kafka Consumer
Offset
Worker
DLQ
```

并且 Metric Label 强制低基数（Low Cardinality），不允许：

```text
user_id
job_id
run_id
query
prompt
Kafka offset
exception text
```

进入 Label。

## Durable Trace

最值得讲：

```text
HTTP Trace
↓
PostgreSQL Job + Outbox
↓
traceparent / tracestate persisted
↓
Publisher
↓
Kafka Header
↓
Worker
```

即使：

```text
HTTP request已经结束
Publisher是另一个进程
Worker晚几秒运行
```

依然属于同一个 Distributed Trace。

------

# 11. Liveness 和 Readiness

这是很典型的后端面试题。

## Liveness

回答：

> **这个进程活着吗？**

所以 `/health`：

```text
process/lifecycle only
```

PostgreSQL 挂了，不代表进程死了。

## Readiness

回答：

> **这个实例现在能接业务吗？**

API Readiness：

```text
PostgreSQL required
Redis limiter required
Runtime accepting required

Redis cache only degraded
Kafka不是API直接依赖
```

Publisher：

```text
PostgreSQL + Kafka
```

Worker：

```text
PostgreSQL + Kafka
```



一句话：

> **Liveness 决定要不要重启，Readiness 决定要不要给流量。**

------

# 12. WP7 — Docker Compose

从这一 WP 开始，项目不只是“代码可以运行”，而是形成真正部署拓扑。

同一个 Python 3.12 Image：

```text
API
Publisher
Worker
Migration
Kafka Init
```

通过不同命令运行。

Compose：

```text
PostgreSQL
Redis
Kafka
Migrate
Kafka Init
API
Publisher
Worker
```

数据库、中间件不默认暴露 Host Port。

Application：

```text
non-root UID 10001
no privileged
no Docker socket
no host network
```



### 面试核心

> 为什么一套 Image 多角色，而不是 API/Worker 各做一个 Image？

因为代码和依赖主体相同，多 Image 容易版本漂移。一个 Immutable Image + 不同 Entrypoint/Command，更容易保证 Deployment Consistency。

------

# 13. WP8 — Kubernetes

WP8 最后不是“写了 YAML”，而是真正在 Docker Desktop Kubernetes 上验证。

真实验证：

```text
Migration Job complete
Kafka Init complete

API Available
Publisher Available
Worker Available

HTTP health 200
readiness 200
metrics 200

Pod recovery PASS

Kafka outage / recovery PASS

Worker
1 → 2 → 1
PASS
```



但是 API：

```text
replicas = 1
strategy = Recreate
```

没有声称：

```text
API Horizontal Scale
Zero-downtime rollout
```

原因并不是 Kubernetes 不会扩容，而是 Agent Runtime 仍然存在：

```text
process-local RunRegistry
Approval Controller
Execution Claim
```

所以多 API Replica 会产生 Authority 问题。

这就是：

> **部署能 Scale，不代表应用语义允许 Scale。**

Replica Matrix：

```text
API
→ 1 active
→ 不支持水平扩展

Publisher
→ 默认1
→ overlap safe foundation

Worker
→ 可以水平扩展
→ 1→2→1真实验证
```



------

# 14. WP9 — Stage6 Final Gate

WP9 不是新功能 WP，而是一次完整的 Distributed Backend Final Gate。

最终真实基础设施包括：

```text
PostgreSQL REAL
Redis REAL
Kafka REAL
Docker Compose REAL
Kubernetes REAL
Prometheus / OTel REAL
```



Broad Regression 只执行了一次：

```text
73 passed
3 failed
```

最终发现：

```text
1 REAL REGRESSION
2 TEST OBSOLESCENCE
```

真实 Regression 是：

> RAG Cache Lookup 消耗了一部分 Runtime Budget 后，Cache Miss 的 Origin Retrieval 又重新拿完整 requested timeout，可能超过 Run 剩余 Deadline。

最终修成：

```text
Origin timeout
≤
Run remaining budget
```



这个 Bug 很值得面试讲，因为它说明：

> **Timeout 不是每个组件各算自己的秒数，而应该服从整个 Request / Run 的 Deadline Budget。**

------

# 15. WP10 — Agent Security / Prompt Injection

这里开始是 Stage6 Supplement。

WP10 最大的认知：

> **不要试图证明模型永远不会被 Prompt Injection，而要保证模型即使被诱导也突破不了 Runtime Authority。**

构建：

```text
Trusted Instruction
User Content
Untrusted External Content
```

RAG / Tool / MCP 等外部内容不能升级成 System Authority。

`PromptInjectionDetector` 只是：

```text
Signal / Evidence
```

不能：

```text
ALLOW
DENY
提升权限
修改 Governance
```

Final Review 专门修复了 Detector 曾参与 Semantic Memory Deny 的问题。

同时引入：

```text
EXTERNAL_NETWORK
DATA_EGRESS
```

其中：

```text
DATA_EGRESS
→ HIGH
→ APPROVAL_REQUIRED
```



核心思想：

```text
Soft Defense
System Prompt / Wrapper / Detector

Hard Defense
Auth / Governance / HITL / Execution
```

------

# 16. WP11 — Context Engineering

WP11 解决的不是“怎么写 Prompt”，而是：

> **一次模型调用到底给模型看什么？**

最终 Context：

```text
System
Security
Current User Request
History
Memory
RAG
Tool Result
Multi-Agent Result
```

都进入明确 Budget / Priority。

Mandatory：

```text
System
Security Instruction
Current User Request
```

不能为了塞进 Context 而静默截断。

History：

```text
保留最近完整 Turn
超限从最老 Turn 开始 Drop
```

RAG：

```text
Retriever决定相关性
ContextBuilder只决定这次放多少
```

Memory 同理。

Final Review 还保证最终真正发送到 Provider 的完整 Wire Message 才是最后 Budget Gate，而且使用**实际选中模型的 Context Window**。

------

# 17. Prompt Identity 与 Structured Output

WP11 还补了：

```text
prompt_id
prompt_version
prompt_digest
```

用于回答：

> 这次结果到底使用了哪个 Prompt Policy？

但 Digest 只针对 Code-owned Prompt，不包含用户/RAG/Memory/Tool 正文。

Structured Output：

```text
Model
↓
Strict Domain Parser
↓
失败
↓
最多一次 Repair
↓
Same Parser
↓
仍失败
↓
Typed Fail
```

Planner / Formation / Forget 的 Parser 仍然拥有 Schema Authority。

Transport Fallback 不能绕过 Schema Validation。

------

# 18. WP12 — Sandbox / Isolated Tool Execution

WP12 补齐最后一层执行安全。

最重要的一句话：

> **Governance 决定“能不能做”，Sandbox 决定“允许做以后最多能影响到哪里”。**

调用链：

```text
ToolGovernance
↓
HITL
↓
ToolExecutionService
↓
ToolAttemptExecutor
↓
Execution Backend
├─ TrustedInProcess
└─ DockerIsolated
```



Docker Sandbox 真正实现：

```text
read-only rootfs
non-root
cap-drop ALL
no-new-privileges

read-only input
dedicated writable output

network none

CPU / Memory / PIDs limits

no Agent env inheritance

bounded output

timeout/cancel
→ docker rm -f
→ inspect verify
```



但明确：

```text
MCP Sandbox = NO
all Tool isolated = NO
hard disk quota = NO
domain/IP allowlist = NO
production sandbox executor = NO
```



这才是正确的 Truth Boundary。

------

# 19. Stage6 最重要的工程方法

如果整个 Stage6 只能记住五件事，我建议记这五个。

## 第一：Authority 必须唯一

例如：

```text
PostgreSQL
= Durable Business Truth

Kafka
= Delivery

Redis
= Cache / Admission

Metric / Trace
= Observation
```

不能因为 Kafka 里有 Job Event，就让 Kafka 变成 Job Authority。

------

## 第二：Cache 和 Queue 都不能伪装数据库

Redis：

```text
可以丢
```

Kafka：

```text
可以重复
```

因此真正的 durable state 必须回到 PostgreSQL。

------

## 第三：Exactly-Once 要非常谨慎

项目真实语义：

```text
At-Least-Once Delivery
+
Dedup
+
Idempotency
+
Lease/Fencing
```

不能因为 Producer 开了 Idempotence 就说：

```text
End-to-End Exactly-Once
```

------

## 第四：Timeout 必须是 Deadline Budget

错误：

```text
RAG 3s
Tool 3s
Model 10s
```

各模块都拿完整 Timeout。

正确：

```text
Run Deadline
   ↓
remaining budget
   ↓
每个下游操作只能消费剩余部分
```

------

## 第五：Authorization 和 Containment 是两回事

```text
Auth
Governance
HITL
```

解决：

> 是否允许做。

```text
Sandbox
```

解决：

> 允许以后最多做到哪。

------

# 20. 30 秒 Stage6 面试回答

Stage6 我主要把原本单机的 Agent Runtime 向生产后端平台演进。

数据层把 Memory、Journal、Job 和 Outbox 等持久状态迁到 PostgreSQL，并加入 JWT、RBAC 和对象 Ownership；Redis 只做 RAG Cache 和 Principal 限流。异步任务采用 Transactional Outbox + Kafka，消息是 At-Least-Once，通过 PostgreSQL Dedup、Lease 和 Fencing 保证重复消息不会重复产生最终业务结果。

工程侧接入 Prometheus、OpenTelemetry、Docker Compose 和 Kubernetes，并真实验证 Worker 多副本。

后面又补了 Prompt Injection 防御、Context Engineering 和 Docker Sandbox，把模型上下文、Tool Governance 和执行隔离串成完整安全链。

------

# 21. 2 分钟 Stage6 面试回答

Stage6 的核心目标是把已经比较完整的 Agent Runtime 做成一个可靠的后端系统。

数据库方面，我用 PostgreSQL 替换了 Runtime 中原有的 SQLite Production Authority，Memory、Journal、Snapshot、Checkpoint 以及后续的 User、Job、Result、Outbox 和 Consumer Dedup 都由 PostgreSQL 管理。Transaction Owner 放在 Application Service，而 Repository 不自行 Commit。

身份层增加 EdDSA JWT、PostgreSQL Principal、RBAC 和 Object Ownership，客户端传入的 actor_id 不作为真实身份。

Redis 只承担两个明确职责，一个是 RAG Cache-Aside，故障时 Fail Open 回源；另一个是 Principal 维度 Lua Token Bucket，Limiter 故障时 Fail Closed。

异步任务上，我没有直接做数据库和 Kafka 双写，而是先在同一 PostgreSQL Transaction 中写 Job 和 Outbox，由独立 Publisher 发送 Kafka。Kafka 使用 At-Least-Once，Worker 在 PostgreSQL Transaction 中做 Dedup、Lease/Fencing 和结果提交，之后才提交 Kafka Offset，所以没有声称 End-to-End Exactly-Once。

然后接入 Prometheus 和 OpenTelemetry，把 HTTP、Outbox、Kafka、Worker 串成 Durable Distributed Trace，并通过 Docker Compose 和 Kubernetes 做真实部署。Worker 做过 1→2→1 横向扩容，但 API 因为 Run 和 Approval Owner 还是 Process-local，所以明确保持单 Active Replica。

最后三个 Supplement 分别解决 Prompt Injection、Context Budget 和 Sandbox，让整个链路从模型输入到 Tool 执行都有明确安全边界。

------

# 22. 高频面试问答

### PostgreSQL、Redis、Kafka 分别负责什么？

```text
PostgreSQL → Durable State
Redis      → Cache / Rate Limit
Kafka      → Message Delivery
```

------

### 为什么 Job 和 Outbox 必须同事务？

否则会产生数据库状态和消息发送状态不一致。

------

### 为什么 Kafka Offset 在 DB Commit 后提交？

避免消息被认为消费完成，但业务结果实际还没落库。

------

### Kafka 是不是 Exactly-Once？

不是，当前明确是 At-Least-Once + Consumer Dedup。

------

### Redis 挂了怎么办？

Cache Fail Open；Rate Limiter Fail Closed。

------

### 为什么 API 不扩成多副本？

因为 RunRegistry / Approval Execution 等仍有 Process-local Owner，多副本会破坏 Authority。

------

### Worker 为什么可以多副本？

Kafka Consumer Group + PostgreSQL Lease/Fencing/Dedup 能协调多个 Worker。

------

### Liveness / Readiness 区别？

Liveness 看进程是否需要重启；Readiness 看实例能否接业务。

------

### Prompt Injection 怎么解决？

不依赖模型绝对拒绝，而是限制外部内容 Authority，并用 Governance/HITL 保护真实 Side Effect。

------

### Context 太长怎么办？

Mandatory 指令完整保留，History recent-first，RAG/Memory 按完整候选确定性降级。

------

### Sandbox 和 Governance 区别？

Governance 是授权，Sandbox 是执行范围限制。

------

# 23. 典型 Bad Case

**DB + Kafka 直接双写**：其中一边成功、一边失败，产生不一致。

**Kafka ACK 就认为业务成功**：Broker 接收消息和业务数据库完成不是同一事实。

**Redis 做业务 Authority**：Cache 丢失会导致业务事实丢失。

**Producer Idempotence = Exactly-Once**：错误，仍然存在跨系统 Crash Window。

**Readiness = Liveness**：数据库短暂异常导致 Pod 无限重启。

**K8s replicas=3 就叫支持水平扩容**：应用内部 Owner 仍 Process-local 时不能这么说。

**System Prompt 防住 Prompt Injection**：只能算软防御。

**Docker 不可用就退回进程内**：在安全边界最需要时自动关闭安全边界。

------

# 24. Stage6 Truth Boundary

现在可以真实声称：

```text
PostgreSQL Async Canonical Persistence

EdDSA JWT / Principal / RBAC / Ownership

Redis RAG Cache
Redis Principal Rate Limiting

Durable Evaluation Job

Transactional Outbox

Kafka At-Least-Once

Consumer Dedup

Lease / Fencing

DLQ

Prometheus

OpenTelemetry

Durable Distributed Trace

Docker Compose

Real Kubernetes Deployment

Worker Horizontal Scaling Foundation

Prompt Injection Trust Boundary

Data Egress Governance

Context Engineering

Final Provider Context Budget Gate

Prompt Identity

Bounded Structured-output Repair

Real Docker Isolated Tool Backend

Filesystem / Network / Environment Containment
```

Stage6 主线 Final Gate 明确确认 PostgreSQL、Redis、Kafka、Docker、Kubernetes 和 Prometheus/OTel 都有真实证据，而不是 Mock-only。

------

# 25. 不能声称什么

主线 Final Gate 已明确禁止：

```text
❌ End-to-End Exactly-Once

❌ API Horizontal Scaling

❌ Zero-Downtime API Rollout

❌ Production PostgreSQL HA

❌ Production Redis HA

❌ Production Kafka HA

❌ HPA Autoscaling

❌ Production Capacity Benchmark

❌ Real-model Kubernetes Deployment E2E
```



Supplement 还要补充不能声称：

```text
❌ MCP 已 Sandbox

❌ 所有 Tool 都 Sandbox

❌ 完整 DLP

❌ Domain/IP Network Allowlist

❌ Hard Disk Quota

❌ Production Sandbox Executor

❌ Provider Exact Tokenizer

❌ Provider-native Structured Output
   （当前 Remote Engine 没有真实实现）
```

------

# 26. Known Limitations

Stage6 主线最终保留 `ACCEPTED_P1 = 4`。主要边界包括：

- PostgreSQL 没有单独做 Lock Contention Fault Injection，也不是所有 DB Operation 都继承 HTTP Deadline；
- Auth 仍存在 Conversation Namespace / Owner Binding 等历史边界，没有做完整 Password / Refresh / OAuth 产品体系；
- API 仍是 Single Active Replica + `Recreate`；
- 没有 HPA、Ingress、PDB、NetworkPolicy、Helm，以及 Production PG/Redis/Kafka HA、Capacity Benchmark 和 Real-model Deployment E2E。

而后来的三个 Supplement 分别收口为：

```text
WP10 ACCEPTED_P1 = 0
WP11 ACCEPTED_P1 = 0
WP12 ACCEPTED_P1 = NONE
```

它们仍然存在 Scope 外 Known Limitation，但不是未关闭 P1。

------

# 27. Stage6 最有价值的面试关键词

不需要全背，重点是能围绕它们讲工程故事：

**后端基础：**

```
Async SQLAlchemy`、`PostgreSQL`、`Unit of Work`、`Transaction Boundary`、`JWT`、`RBAC`、`Object Ownership
```

**分布式：**

```
Transactional Outbox`、`At-Least-Once`、`Consumer Dedup`、`Idempotency`、`Lease`、`Fencing`、`Manual Offset Commit`、`DLQ
```

**流量与可靠性：**

```
Cache-Aside`、`Token Bucket`、`Fail Open`、`Fail Closed`、`Deadline Budget
```

**可观测性：**

```
Prometheus`、`OpenTelemetry`、`Trace Context`、`Low Cardinality`、`Liveness`、`Readiness
```

**部署：**

```
Docker Compose`、`Kubernetes`、`Migration Job`、`RollingUpdate`、`Recreate`、`Horizontal Scaling
```

**Agent：**

```
Prompt Injection`、`Trust Boundary`、`Context Engineering`、`Token Budget`、`Prompt Identity`、`Structured Output`、`Tool Governance`、`HITL`、`Sandbox
```

------

# 28. 如果面试只能准备 12 道 Stage6 题

我会优先准备：

1. **为什么 PostgreSQL、Redis、Kafka 的 Authority 必须分开？**
2. **为什么 Repository 不应该 Commit？**
3. **Transactional Outbox 解决了什么问题？**
4. **为什么 Kafka 只能声称 At-Least-Once？**
5. **Consumer Dedup、Idempotency、Lease、Fencing 分别解决什么？**
6. **Redis Cache 为什么 Fail Open，而 Limiter 为什么 Fail Closed？**
7. **Liveness 和 Readiness 有什么区别？**
8. **为什么 Worker 可以水平扩展，但 API 目前不能？**
9. **Distributed Trace 如何跨 PostgreSQL Outbox + Kafka 保持？**
10. **Prompt Injection 为什么不能只靠 System Prompt？**
11. **Context Window 不够时你怎么选择上下文？**
12. **Tool Governance 和 Sandbox 为什么必须分开？**

这 12 道基本能把整个 Stage6 串起来。

------

# 29. Stage6 的真正项目叙事

不要面试时按：

> “WP1 做 PG，WP2 做 JWT，WP3 做 Redis……”

这种流水账讲。

更推荐讲成四次演进：

### 第一层：把 Agent 状态变成可靠的 Durable State

```text
SQLite
→ PostgreSQL
→ Transaction
→ Auth / Ownership
```

### 第二层：把同步 Agent Backend 变成可靠异步系统

```text
Durable Job
→ Transactional Outbox
→ Kafka
→ Dedup / Lease / Fencing
```

### 第三层：让它真的可以运行和运维

```text
Prometheus / OTel
→ Docker
→ Kubernetes
→ Worker Scaling
```

### 第四层：把 Agent 特有的生产风险补齐

```text
Prompt Injection
→ Context Engineering
→ Tool Governance
→ Sandbox
```

这样整个项目的故事会非常完整。

------

# 30. 一句话总结整个 Stage6

> **Stage6 把 LocalAgent 从一个功能完整的单机 Agent Runtime，演进成了以 PostgreSQL 为持久状态权威、Redis 负责缓存和流量治理、Kafka 承载可靠异步任务，并具备认证授权、事务一致性、可观测性、Docker/Kubernetes 部署以及 Prompt Injection、Context Engineering 和 Sandbox 安全边界的 AI Agent 后端平台；同时明确保留 At-Least-Once、Single-Active API 和非生产 HA 等真实边界，不把工程能力过度包装成尚未实现的生产保证。**