# Stage6-WP6 — Backend Observability & Reliability

## 后端可观测性与可靠性学习 / 面试总结

------

# 1. 名词 / 概念速览

**可观测性（Observability）**：通过 Metrics、Trace、Logs 判断系统内部发生了什么，而不是让这些信号参与业务决策。

**指标（Metrics）**：低成本、可聚合的时间序列数据，例如请求量、失败率、延迟、Kafka ACK 数。

**追踪（Distributed Tracing）**：通过 Trace / Span 关联一个请求跨 HTTP、数据库、消息队列和 Worker 的执行路径。

**结构化日志（Structured Logging）**：用稳定字段记录运行事件，方便搜索、聚合和关联 Trace。

**Prometheus**：本项目用于暴露 Metrics 的 Pull-based 监控体系。

**OpenTelemetry（OTel）**：本项目用于产生、传播和导出 Trace 的标准化可观测性框架。

**Trace ID**：一次分布式调用链的全局标识。

**Span ID**：Trace 中一次具体操作的标识。

**W3C Trace Context**：跨服务传播 Trace 的标准，本项目使用 `traceparent` 和 `tracestate`。

**指标基数（Cardinality）**：Metric Label 可能产生的不同组合数量；高基数会造成 Prometheus 时间序列爆炸。

**存活探针（Liveness）**：判断进程是否还活着，不代表依赖全部正常。

**就绪探针（Readiness）**：判断当前进程是否具备承担对应流量或任务所需的依赖能力。

**能力语义（Capability Semantics）**：同一个基础设施故障，对不同功能可能具有不同业务含义。

**故障隔离（Failure Isolation）**：Observability 自己失败时不能反向导致业务失败。

**Fail-open**：观测能力失败时业务继续执行。

**Fail-closed**：某个安全/准入 Authority 不可用时拒绝业务请求。

------

# 2. 当前 WP 真实实现

当前三个主要进程：

```text
API
Outbox Publisher
Evaluation Worker
```

每个进程都有一个独立的：

```text
ObservabilityService
```

它负责：

```text
Prometheus Registry
OpenTelemetry TracerProvider
Span Processor / Exporter
Metric Handles
Trace / Log Correlation
Bounded Shutdown
```

不存在：

```text
per-request TracerProvider
per-message Metric Registry
多个竞争的 global provider
```

------

# 3. 当前 Observability 架构

当前整体链路：

```text
HTTP Request
   ↓
Prometheus HTTP Metrics
   ↓
OTel Server Span
   ↓
Job + Outbox
   ↓
Durable traceparent / tracestate
   ↓
Outbox Publisher
   ↓
Kafka Produce Span + Kafka Header
   ↓
Kafka Consumer
   ↓
Worker Process Span
   ↓
Evaluation Execution Span
```

同时日志里会关联：

```text
request_id
trace_id
span_id
```

其中：

```text
request_id
```

仍然是 HTTP Local Correlation Identity；

```text
trace_id
```

是 Distributed Trace Identity。

二者没有被强行合并。

------

# 4. 为什么 Observability 不能成为 Authority

这一点非常重要。

当前：

```text
Metrics
Trace
Logs
```

都只是：

```text
Observation
```

不能参与：

```text
Job 是否执行

Outbox 是否已经发布

Kafka Offset 是否提交

Consumer 是否已经处理

Runtime 是否恢复

Cache 是否命中
```

这些真实 Authority 仍然是：

```text
PostgreSQL
Redis
Kafka Contract
Runtime Event / Journal
```

Final Review 明确确认 OTel 不参与 Job、Outbox、Offset、Dedup、Journal、Semantic Trace 或 Recovery 判定。

一句话：

> Observability 可以告诉你系统发生了什么，但不能决定系统应该做什么。

------

# 5. Prometheus Metrics 当前覆盖什么

当前真实 Metrics 覆盖：

```text
HTTP

Redis Cache
Redis Rate Limiter

Job

Outbox

Kafka Producer

Kafka Consumer

Kafka Offset

Worker

DLQ
```

而且成功指标不是“代码执行到某一行就算成功”，而是绑定真实业务边界。

例如：

```text
Kafka acked
```

只有 Broker ACK 成功才记录。

```text
Outbox publish success
```

只有 PostgreSQL `mark_published` 事务提交后才记录。

```text
Offset commit success
```

只有同步 Commit 且所有 Partition 无错误才记录。

这是非常重要的指标设计原则：

> Metric Success Boundary 必须和真实 Business Success Boundary 一致。

------

# 6. 为什么“提前记 success”是错的

错误：

```text
producer.produce()
↓
metric success +1
↓
Broker 最终失败
```

结果：

Metrics 告诉你：

```text
成功
```

真实业务：

```text
失败
```

这类 Metrics 会让事故排查更加困难。

所以当前所有关键 Success Metric 都在真实 Durable / ACK 边界之后记录。

------

# 7. 什么是 Metric Cardinality

假设 Metric：

```text
http_requests_total{
  user_id="..."
}
```

如果有 100 万用户：

```text
100 万条 Time Series
```

再加：

```text
path
method
status
job_id
trace_id
```

组合数量会指数式扩大。

这就是：

```text
High Cardinality
```

Prometheus 最怕的不是“指标很多”，而是：

> Label Value 的不同组合无限增长。

------

# 8. 当前 Cardinality Policy

当前禁止以下字段进入 Metric Label：

```text
request_id

trace_id
span_id

user_id
principal_id

job_id
event_id
run_id
approval_id

query
prompt

raw URL

Redis key

Kafka offset

worker UUID

claim token

exception text
```

允许的基本都是：

```text
method
route template
status class
fixed outcome
fixed reason
fixed capability
```

这是典型的：

```text
bounded label domain
```

------

# 9. 为什么 HTTP 要用 Route Template

假设：

```text
/api/evaluation/jobs/123
/api/evaluation/jobs/456
/api/evaluation/jobs/789
```

如果 Label 使用：

```text
raw path
```

每个 Job 都产生新的 Time Series。

当前统一归一到：

```text
/api/evaluation/jobs/{job_id}
```

这样无论多少 Job：

```text
route label
```

仍然只有一个值。

------

# 10. Metrics 和 Durable Truth 的区别

例如：

```text
Queued Job Count
```

如果只做：

```text
process local counter += 1
```

在：

```text
API Process A
Worker Process B
Publisher Process C
```

多进程情况下，这个 Counter 并不能代表整个系统真实 Backlog。

因此当前没有用 process-local Counter 冒充：

```text
Durable Job Backlog
Outbox Backlog
```

如果未来要做：

```text
outbox_pending
oldest_job_age
```

应该定期从 PostgreSQL Durable State 采样。

------

# 11. OpenTelemetry 当前做了什么

当前是真实：

```text
TracerProvider
```

而不是：

```text
OTel API + No-op Tracer
```

同时有：

```text
ParentBased(
    TraceIdRatioBased(...)
)
```

的可配置 Sampling。

测试使用真实 InMemory Exporter；

生产可选：

```text
OTLP/HTTP
+
BatchSpanProcessor
```

------

# 12. Trace Exporter 挂了怎么办

这是 WP6 很关键的可靠性原则：

```text
OTLP Collector Down
```

不能导致：

```text
HTTP 500

Job FAILED

Kafka Worker FAILED
```

Observability Backend 不是业务 Authority。

所以：

```text
Exporter failure
=
fail-open
```

Final Review 还额外增加了：

```text
localagent_otel_span_export_total{
  outcome=success|failure
}
```

也就是说：

> Exporter 自己失败也必须可观测，但不能影响业务。

------

# 13. 为什么需要 fail_open_span

原先一个潜在问题：

```text
start span
↓
OTel helper throws
↓
business operation also fails
```

这是错误设计。

现在集中使用：

```text
fail_open_span
```

保证：

```text
Span 创建失败
Span enter/exit 失败
Exporter 异常
```

都不会改变原始 Business Result 或 Business Exception。

------

# 14. Trace Context 为什么要持久化

普通同步服务：

```text
Service A
→ HTTP
→ Service B
```

Trace Context 可以直接通过 HTTP Header 传播。

但当前链路：

```text
HTTP
↓
PostgreSQL Outbox
↓
过几秒 / 几分钟
↓
Publisher
↓
Kafka
↓
Worker
```

中间：

```text
API Process Context
```

早就不存在了。

如果 Trace Context 只存在：

```text
ContextVar
Memory
Current Span
```

跨 Outbox 后一定丢失。

所以当前在 Job + Outbox 的 PostgreSQL Transaction 中持久化：

```text
traceparent
tracestate
```

------

# 15. 当前 Trace Propagation 链

真实路径：

```text
HTTP server span

↓ persist

PostgreSQL Outbox
traceparent
tracestate

↓ restore

Outbox Publisher

↓ inject

Kafka Headers

↓ extract

Kafka Worker

↓

Evaluation Execution
```

而且已经真实验证：

```text
API Span 已结束
Publisher / Worker 使用全新 Observability Owner
```

以后，这些 Span 仍然属于同一个 Distributed Trace。

------

# 16. 为什么只持久化 traceparent / tracestate

当前明确没有持久化：

```text
Baggage
User identity
JWT
Query
Prompt
```

因为 Trace Context 的目标是：

```text
关联执行链
```

而不是复制业务上下文。

所以当前 Durable Trace Context：

```text
最小
标准化
低敏感
```

------

# 17. Trace Context 损坏怎么办

如果 Kafka Header：

```text
missing
malformed
```

业务不能失败。

正确：

```text
Trace Context invalid
↓
Start new trace
↓
Business continues
```

因为 Trace Context：

```text
Observability Metadata
```

不是：

```text
Message Validity Authority
```

Final Review 已确认缺失或 malformed trace context 不影响消息有效性。

------

# 18. Logs 和 Trace 如何关联

当前关键 Structured Log 会加入：

```text
trace_id
span_id
```

HTTP Log 同时保留：

```text
request_id
```

因此排障时可以：

```text
Metrics
↓
发现错误率上升

Trace
↓
找到慢 / 失败调用链

Logs
↓
查看具体事件上下文
```

三种 Signal 各自承担不同职责。

------

# 19. Metrics、Trace、Logs 如何分工

## Metrics

回答：

```text
有没有问题？
问题多严重？
趋势是什么？
```

比如：

```text
Kafka publish failure rate
HTTP p95 latency
DLQ count
```

------

## Trace

回答：

```text
问题发生在哪一段调用链？
```

比如：

```text
HTTP
→ Outbox
→ Kafka
→ Worker
```

哪一步特别慢。

------

## Logs

回答：

```text
这一次具体发生了什么？
```

例如：

```text
outbox stale claim
worker timeout
limiter unavailable
```

------

# 20. Liveness 和 Readiness 有什么区别

这是高频面试题。

当前：

```text
/health
```

是：

```text
Liveness
```

它只回答：

> 这个进程是不是还活着？

不会去 Ping：

```text
PostgreSQL
Redis
Kafka
OTLP
```

如果 PostgreSQL 挂了：

进程仍然：

```text
alive
```

只是：

```text
not ready
```

------

# 21. 为什么 Liveness 不能检查所有依赖

假设：

```text
Kafka 短暂故障
```

Liveness 返回失败。

Kubernetes：

```text
restart container
```

但 Kafka 仍然挂着。

新进程：

```text
启动
→ health fail
→ restart
```

最终形成：

```text
restart storm
```

所以：

```text
Liveness
=
进程自身健康
```

而：

```text
Readiness
=
能否承担当前职责
```

------

# 22. API Readiness 当前需要什么

API：

```text
PostgreSQL
Redis Limiter
Runtime Accepting
```

其中：

### PostgreSQL

因为负责：

```text
Identity
Ownership
Jobs
Persistence
```

### Redis Limiter

因为它是：

```text
Admission Authority
```

失效时按照 WP3 Contract：

```text
fail-closed
```

### Runtime Accepting

防止已经进入 Shutdown 的 Runtime 仍接受新工作。

------

# 23. 为什么 Kafka Down 不影响 API Ready

这是一个很好的架构面试点。

API 提交异步任务时：

```text
API
↓
PostgreSQL Job
+
Transactional Outbox
```

不需要同步 Kafka Publish。

因此：

```text
Kafka Down
```

时：

```text
API
仍可以 durable accept Job
```

Publisher 之后再 Retry Kafka。

所以 Kafka：

```text
NOT API readiness dependency
```

这也是 Transactional Outbox 带来的解耦价值。

------

# 24. Redis Cache 和 Limiter 为什么健康语义不同

即使二者底层：

```text
共用 Redis
```

业务语义不同。

Cache Redis Down：

```text
Cache unavailable
↓
Fallback origin retrieval
```

属于：

```text
DEGRADED
```

Rate Limiter Redis Down：

```text
无法判断 admission
```

根据安全策略：

```text
fail-closed
```

所以：

```text
UNAVAILABLE
```

最终 API Not Ready。

------

# 25. 为什么健康检查按 Capability 建模

错误：

```text
redis = down
```

这种粒度太粗。

当前更合理：

```text
redis_cache = degraded

redis_limiter = unavailable
```

即使它们指向同一个 Redis Instance。

因为真正重要的是：

```text
这个基础设施故障
对什么业务能力造成什么影响
```

这就是：

```text
Capability-aware Readiness
```

------

# 26. Disabled 和 Unavailable 不一样

Final Review 修过一个问题：

原来某个 Redis Capability：

```text
disabled
```

仍然会执行：

```text
PING Redis
```

这是错误的。

现在：

```text
disabled
→ no I/O
→ status healthy
→ reason=disabled
```

区别：

```text
Disabled
=
我们根本没有启用这个能力

Unavailable
=
我们需要它，但它挂了
```

------

# 27. Publisher / Worker Readiness

Publisher 必需：

```text
PostgreSQL
Kafka Job Topic
```

Worker 必需：

```text
PostgreSQL
Kafka Consumer Topic
```

两者都：

```text
不依赖 Redis
```

这符合真实 Process Responsibility。

------

# 28. Health Check 为什么必须 Read-only

Health Check 不能：

```text
创建 Job

写 Outbox

发 Kafka Test Message

修改 Redis Rate Limit State
```

当前使用：

```text
PostgreSQL → SELECT 1

Redis → PING

Kafka → full metadata lookup
```

目标：

> Health Check 只观察，不产生业务副作用。

------

# 29. Kafka Health Check 为什么不能自动建 Topic

如果 Health Check：

```text
check missing topic
```

却因为 Broker Auto-create：

```text
顺手把 Topic 创建了
```

健康检查实际上改变了系统状态。

当前使用：

```text
full metadata
```

只读检查 Topic 是否存在。

------

# 30. Health Check 为什么必须有 Timeout

错误：

```text
/readyz
→ PostgreSQL connection hang
→ HTTP request never returns
```

编排系统无法判断：

```text
ready
还是 not ready
```

所以所有依赖检查都：

```text
asyncio.timeout
+
底层 client timeout
```

双重有界。

------

# 31. Healthcheck CLI 为什么有价值

Publisher / Worker 不是 HTTP Server。

为了健康检查，不应该：

```text
每个 Process 再启动一个 FastAPI
```

当前提供 CLI：

```text
uv run python -m scripts.healthcheck --component api

uv run python -m scripts.healthcheck --component publisher

uv run python -m scripts.healthcheck --component worker
```

返回：

```text
0 = ready

1 = not ready
```

之后 Docker / Kubernetes 可以直接使用这些 Contract。

------

# 32. 为什么 API CLI 不能自己假设 Runtime Ready

Final Review 实际修过：

```text
API healthcheck CLI
默认 runtime_ready=True
```

这会出现：

```text
Runtime 根本没起来
↓
CLI 仍说 ready
```

最终改成真正读取：

```text
API /readyz
```

------

# 33. Observability Failure Isolation

当前确认以下故障都可观测：

```text
Cache Redis failure

Limiter Redis failure

PostgreSQL readiness failure

Kafka Producer failure

Outbox failure

Worker timeout

DLQ failure

OTel exporter failure
```

同时这些 Observability Helper 自己失败：

```text
不能改变业务状态
```

------

# 34. 为什么 Observability 自己也要被观测

比如：

```text
OTel exporter 一直失败
```

如果完全 Fail-open 且没有任何指标：

业务没问题，但：

```text
Trace 全丢了
```

你可能很久都不知道。

所以 Final Review 加了：

```text
localagent_otel_span_export_total{
  outcome=success|failure
}
```

这就是：

> Observability of Observability。

------

# 35. Kafka Assignment Race 最后是什么结论

之前真实 Kafka Test 出现一次：

```text
two-consumer assignment race
```

Final Review 没有因为：

```text
rerun passed
```

就直接忽略。

最终分析发现：

测试在两个 Consumer Assignment 都稳定前：

```text
就开始 poll
```

唯一 Message 被一个 Consumer 取走后，测试又因为另一个 Consumer 尚未 Assignment 而丢弃本地引用。

最终修成：

```text
wait both assignments stable
↓
publish message
↓
start processing
```

分类：

```text
TEST_FLAKE_ONLY
```

生产 Consumer / Rebalance / PG Fencing 没有修改。

------

# 36. 工程构建方法类问答

## Q1：Metrics、Trace、Log 分别解决什么问题？

Metrics 发现趋势和异常；Trace 定位一次请求跨系统走到了哪里；Log 提供具体上下文和事件细节。

------

## Q2：为什么 Metric Label 不能放 job_id？

因为不同 Job 会产生无限 Time Series，造成高 Cardinality 和 Prometheus 存储/查询压力。

------

## Q3：为什么 Trace Context 要存 PostgreSQL？

因为 HTTP 到 Outbox/Kafka/Worker 是异步跨进程链路，内存 Context 无法跨越 Durable Queue 和进程重启。

------

## Q4：为什么 OTel Exporter Down 不能影响业务？

Observability 不是 Business Authority，Collector 故障不应该导致 HTTP/Job/Kafka 失败。

------

## Q5：Liveness 和 Readiness 有什么区别？

Liveness 判断进程是否还活着；Readiness 判断这个进程是否具备承担当前职责的必要依赖。

------

## Q6：为什么 Kafka Down 不让 API Not Ready？

API 先把 Job+Outbox 原子写入 PostgreSQL，Kafka 是异步 Publisher 的依赖，不是 API Durable Admission 的同步依赖。

------

## Q7：为什么 Redis Cache 和 Limiter 不能共用一个 Health 状态？

虽然底层都是 Redis，但 Cache 故障可以回源，Limiter 故障会失去 Admission Authority，两者业务语义不同。

------

## Q8：为什么 `/metrics` 不能实时查询所有依赖？

Prometheus Scrape 会频繁执行；如果每次 Scrape 都访问 PG/Redis/Kafka，会让监控系统本身给业务依赖制造压力。

------

## Q9：为什么 OTel 不替代 Runtime Journal？

Journal 是业务/恢复 Evidence；OTel 是可观测性 Trace，两者用途和 Authority 完全不同。

------

## Q10：为什么健康检查不能发测试 Kafka 消息？

因为 Health Check 应该 Read-only，不能通过检测动作改变系统业务状态。

------

# 37. 30 秒面试回答

我在 LocalAgent 里做了统一的 Backend Observability。API、Outbox Publisher 和 Kafka Worker 每个进程都有独立的 Observability Owner，使用 Prometheus 和 OpenTelemetry。

Metrics 的重点不是数量，而是成功边界和 Cardinality，比如 Kafka Publish 只有收到 Broker ACK 后才记 success，HTTP Metric 使用 Route Template，禁止把 job_id、user_id、trace_id 这类高基数字段放进 Label。

Tracing 方面，我把 W3C `traceparent/tracestate` 和 Outbox 一起持久化到 PostgreSQL，再通过 Kafka Header 传播到 Worker，这样即使进程上下文已经消失，也能串起 HTTP → Outbox → Kafka → Worker。

Health 只判断进程存活，Readiness 则按 Capability 判断，例如 Kafka Down 不影响 API Ready，但会让 Publisher Not Ready；Redis Cache Down 只是 Degraded，Limiter Down 则 Fail-closed。

------

# 38. 2 分钟面试回答

这一阶段我主要解决三个问题：怎么监控、怎么跨异步链路追踪，以及健康检查到底应该表达什么。

Metrics 方面接入了 HTTP、Redis、Job、Outbox、Kafka、Worker 和 DLQ。我比较关注成功边界和 Cardinality，例如 Kafka acked 指标只在 Broker ACK 后增加，Offset success 只在同步 Commit 且 Partition 没有 Error 后记录。所有 Label 都限制为有限枚举或 Route Template，不允许 job_id、user_id、request_id、raw path 之类高基数字段。

Tracing 用 OpenTelemetry，但没有把它当 Runtime Authority。HTTP 请求里的 W3C `traceparent/tracestate` 会和 Job/Outbox 在同一 PostgreSQL Transaction 里持久化，Publisher 后面从数据库恢复 Context，再放进 Kafka Header，Worker 再恢复 Consumer Span。所以即使 API Span 已经结束、Publisher/Worker 重启，也能恢复同一个 Distributed Trace。

Health 方面我区分了 Liveness 和 Readiness。Liveness 只看 Process Lifecycle，不因为 Kafka 或 PostgreSQL 挂了就重启进程；Readiness 按 Process Capability 判断。比如 API 依赖 PostgreSQL、Rate Limiter Redis 和 Runtime Accepting，但不依赖 Kafka，因为 Transactional Outbox 已经把 Kafka 从 API 同步链路里解耦。Redis Cache Down 只是 Degraded，但 Limiter Redis Down 会 Fail-closed，因此虽然共用 Redis，它们还是两个独立 Capability。

另外 Observability 本身全部 Fail-open，OTel Collector 挂了不能反向导致业务失败。

------

# 39. 高频追问 + 简答

### Prometheus 最怕什么？

高 Cardinality，尤其是把用户 ID、Job ID、Trace ID、Raw URL 放到 Label。

### Trace ID 能直接当 Request ID 吗？

不推荐。Request ID 是本地 HTTP Correlation Identity，Trace ID 是 Distributed Trace Identity。

### 为什么不用全自动 OTel Instrumentation？

当前更需要少而准确的生产 Span，避免自动 + 手工 Instrumentation 产生 Duplicate Span。

### Collector Down 怎么办？

Tracing Fail-open，业务继续，但记录 Exporter Failure Metric / Log。

### Kafka Down 为什么 API 还能接 Job？

因为 API 只需要 PostgreSQL 原子提交 Job + Outbox，Kafka Publisher 后续重试。

### Redis Down 为什么 API Not Ready？

因为当前 Cache 和 Limiter 共用 Redis，其中 Limiter 是 Required Admission Authority；虽然 Cache 只是 Degraded，但 Limiter Unavailable 会让 API Not Ready。

### `/metrics` 能不能去实时查 Outbox 数量？

可以未来做采样，但不应该每次 Scrape 都直接执行大量外部查询。

------

# 40. Bad Case / Failure Scenario

## Bad Case 1：Label 放 job_id

```text
1,000,000 Job
→ 1,000,000 Time Series
```

Prometheus Cardinality 爆炸。

------

## Bad Case 2：Exporter Failure 打崩业务

```text
HTTP request
↓
span export fails
↓
HTTP 500
```

错误。

正确：

```text
export failure
→ metric/log
→ business continues
```

------

## Bad Case 3：Trace Context 只存在 Memory

```text
HTTP ends
↓
process context lost
↓
Publisher later publishes
```

Trace 断链。

正确：

```text
persist traceparent/tracestate
with Outbox
```

------

## Bad Case 4：Liveness 检查 Kafka

```text
Kafka outage
→ /health failure
→ container restart
→ Kafka still down
→ restart loop
```

错误。

------

## Bad Case 5：API Readiness 要求 Kafka

```text
Kafka Down
→ API stops accepting durable Job
```

实际上 Transactional Outbox 已经允许 API 独立接受 Job。

------

## Bad Case 6：只输出 redis=down

丢失：

```text
Cache = degraded
Limiter = unavailable
```

这两个不同业务语义。

------

## Bad Case 7：Metrics success 提前

```text
producer.produce()
→ success +1
↓
broker rejects
```

监控数据与真实业务结果不一致。

------

# 41. Truth Boundary

当前真实实现：

```text
✅ Process-scope Observability Owner

✅ Private Prometheus Registry

✅ Real /metrics

✅ HTTP Metrics

✅ Redis Metrics

✅ Job Metrics

✅ Outbox Metrics

✅ Kafka Producer/Consumer Metrics

✅ Worker Metrics

✅ DLQ Metrics

✅ Low-cardinality Label Policy

✅ Real OpenTelemetry SDK

✅ Configurable Sampling

✅ Optional OTLP/HTTP Exporter

✅ Exporter Fail-open

✅ Export Failure Metrics

✅ Structured Log Trace Correlation

✅ W3C traceparent/tracestate

✅ Durable Trace Context in PostgreSQL Outbox

✅ Kafka Trace Headers

✅ Worker Trace Continuation

✅ Process-only Liveness

✅ Capability-aware API Readiness

✅ Publisher Readiness

✅ Worker Readiness

✅ Bounded Read-only Health Checks

✅ Kafka Health No Auto-create

✅ Redis Cache / Limiter Capability Split

✅ Real PostgreSQL Evidence

✅ Real Redis Evidence

✅ Real Kafka Evidence
```

------

# 42. Completion Boundary

最终：

```text
WP6_REVIEW_STATUS = PASS

OBSERVABILITY_OWNER_CONFIRMED = YES

PROMETHEUS_REAL_CONFIRMED = YES
METRICS_ENDPOINT_CONFIRMED = YES

LOW_CARDINALITY_CONFIRMED = YES

OTEL_SDK_CONFIRMED = YES
TRACE_EXPORT_FAIL_OPEN_CONFIRMED = YES

W3C_TRACE_CONTEXT_CONFIRMED = YES

DURABLE_OUTBOX_TRACE_CONTEXT_CONFIRMED = YES

KAFKA_TRACE_PROPAGATION_CONFIRMED = YES

WORKER_TRACE_CONTINUATION_CONFIRMED = YES

TRACE_SENSITIVE_DATA_POLICY_CONFIRMED = YES

LIVENESS_PROCESS_ONLY_CONFIRMED = YES

API_READINESS_SEMANTICS_CONFIRMED = YES

PUBLISHER_READINESS_CONFIRMED = YES

WORKER_READINESS_CONFIRMED = YES

REDIS_CACHE_DEGRADED_SEMANTICS_CONFIRMED = YES

REDIS_LIMITER_REQUIRED_SEMANTICS_CONFIRMED = YES

KAFKA_NOT_API_READY_DEPENDENCY_CONFIRMED = YES

HEALTH_TIMEOUTS_BOUNDED_CONFIRMED = YES

HEALTH_CHECKS_READ_ONLY_CONFIRMED = YES

KAFKA_HEALTH_NO_AUTO_CREATE_CONFIRMED = YES

OBSERVABILITY_BUSINESS_ISOLATION_CONFIRMED = YES

KAFKA_ASSIGNMENT_RACE_CLASSIFICATION = TEST_FLAKE_ONLY

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0

CAN_CLOSE_WP6 = YES
CAN_ENTER_WP7 = YES
```

------

# 43. Known Limitation / ACCEPTED_P1

当前没有：

```text
Grafana

Alertmanager

Production OTel Collector

Hosted APM

HA Observability Backend

Durable Backlog Sampler

Oldest Backlog Age Sampler

Kafka Consumer Lag Dashboard

SQL Statement Auto Tracing

Full Performance Benchmark
```

Publisher / Worker 的 Metrics Endpoint 当前还需要：

```text
--metrics-port
```

显式开启。

这些都是当前 Scope Limitation，不是遗留 P1。

最终：

```text
ACCEPTED_P1 = 0
```

------

# 44. Final Review 修掉的 7 个问题

## 1. Span Helper 可能打崩业务

修成统一：

```text
fail_open_span
```

------

## 2. Exporter Failure 不可见

增加：

```text
localagent_otel_span_export_total
```

和安全日志。

------

## 3. Limiter Unavailable 缺日志

增加固定低基数：

```text
outcome / code
```

不复制 Exception Text。

------

## 4. Healthcheck 初始化可能打印 Traceback

改为：

```text
safe JSON
exit 1
```

------

## 5. API CLI 假设 Runtime Ready

改成读取真实：

```text
/readyz
```

------

## 6. Metrics Path 可覆盖业务 Route

禁止配置：

```text
/api/*
health
docs
```

等固定路径。

------

## 7. Kafka Assignment 测试存在时序 Race

加入：

```text
assignment barrier
```

最终判定：

```text
TEST_FLAKE_ONLY
```

------

# 45. 面试关键词

重点掌握：

```text
Observability

Prometheus

OpenTelemetry

Metrics

Distributed Tracing

Structured Logging

Trace ID

Span ID

W3C Trace Context

traceparent

tracestate

Cardinality

High-cardinality Labels

Route Template

Metric Success Boundary

Fail-open Observability

Liveness

Readiness

Capability-aware Readiness

Dependency Health

Failure Isolation

OTLP

TracerProvider

SpanProcessor

Sampling

BatchSpanProcessor

Trace Propagation

Durable Trace Context

Log Correlation

Observability Authority Boundary
```

------

# 46. WP3～WP6 如何串起来讲

```text
WP3 Redis
→ Cache / Traffic Governance

WP4 PostgreSQL Job + Outbox
→ Durable Async / Dual Write Reliability

WP5 Kafka
→ At-Least-Once / Consumer Idempotency

WP6 Observability
→ 能看到、能追踪、能判断是否可以服务
```

因此完整后端链：

```text
HTTP
↓
Auth
↓
Rate Limiter
↓
PostgreSQL Job
↓
Transactional Outbox
↓
Kafka
↓
Worker
↓
Result

同时：

Prometheus
+
OpenTelemetry
+
Structured Logs
+
Health / Readiness
```

------

# 47. 本 WP 最值得掌握的 10 个问题

优先掌握：

```text
1. Metrics、Trace、Logs 分别解决什么问题？

2. Prometheus 为什么特别怕高 Cardinality？

3. 为什么 Metric Success Boundary 必须和真实业务成功边界一致？

4. 为什么异步 Outbox/Kafka 链路必须持久化 Trace Context？

5. Observability Backend 挂了为什么必须 Fail-open？

6. Liveness 和 Readiness 的本质区别是什么？

7. 为什么 Kafka Down 不应该让 API Not Ready？

8. 为什么 Redis Cache 和 Rate Limiter 即使共用 Redis，也要分开表达健康状态？

9. 为什么 Health Check 必须 Read-only、Bounded？

10. 为什么 OTel Trace 不能替代 Journal / Runtime Event？
```

最值得记住的一句话：

> **可观测性系统的职责是准确告诉你业务发生了什么，而不是参与决定业务应该怎么运行；所以指标必须低基数、Trace 必须跨进程可恢复、健康检查必须符合真实依赖语义，而 Observability 自身失败必须与业务正确性隔离。**