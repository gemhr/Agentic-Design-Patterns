# Stage6-WP3 — Redis Cache & Traffic Governance

## Redis 缓存与流量治理学习 / 面试总结

------

# 1. 名词 / 概念速览

**Redis**：本 WP 中作为可丢弃缓存和分布式限流状态存储使用，不是业务数据 Authority。

**异步 Redis 客户端（Async Redis Client）**：使用 `redis.asyncio` 与 Redis 通信，避免阻塞 ASGI Event Loop。

**连接池（Connection Pool）**：复用 Redis Connection，并通过最大连接数和 Timeout 控制资源上界。

**旁路缓存（Cache-Aside）**：应用先查缓存，MISS 时调用真实数据源，再把结果写入缓存。

**缓存权威（Cache Authority）**：本项目明确 Redis 不是 Retrieval Authority，删除缓存不会影响系统正确性。

**缓存命中（Cache Hit）**：对应 Key 已有合法缓存，可直接从缓存恢复业务结果。

**缓存未命中（Cache Miss）**：Key 不存在、损坏、版本不兼容或不允许缓存，需要回源。

**授权域（Authorization Domain）**：用于隔离不同用户缓存空间，本项目来自 `Principal.authz_domain_id`。

**索引代次（Index Generation）**：RAG 索引版本 Identity；Generation 变化后旧缓存自然失效。

**检索策略摘要（Retrieval Policy Digest）**：把影响 Retrieval Result 的关键参数稳定编码成 Identity。

**查询摘要（Query Digest）**：Normalized Query 的 Hash，不把 Raw Query 暴露到 Redis Key。

**TTL（Time To Live）**：缓存 Key 的有效时间。

**TTL 抖动（TTL Jitter）**：在 TTL 基础上加入小范围随机变化，避免大量 Key 同时过期。

**缓存雪崩（Cache Avalanche）**：大量缓存同时过期，瞬间把请求压力打到后端。

**缓存击穿（Cache Breakdown / Hot Key Expiration）**：高频 Key 失效时大量并发请求同时回源。

**缓存穿透（Cache Penetration）**：大量不存在的数据请求持续绕过缓存命中并打到数据源。

**令牌桶（Token Bucket）**：按容量和补充速率控制请求速率的限流算法。

**Lua 原子脚本（Lua Atomic Script）**：在 Redis 内一次执行读、计算、写操作，避免多个实例间竞态。

**Redis TIME**：由 Redis Server 提供统一时间，避免多个 API 实例本地时钟不一致。

**失败开放（Fail Open）**：组件故障时允许业务继续，例如 Cache Redis 故障后直接回源。

**失败关闭（Fail Closed）**：组件故障时拒绝请求，例如 Rate Limiter 无法工作时返回 503。

**429 Too Many Requests**：明确确认客户端已经超过限流额度。

**503 Service Unavailable**：平台暂时无法安全执行请求，例如限流 Redis 不可用。

**安全缓存投影（Safe Cache Projection）**：只缓存可以跨请求复用的确定性 Retrieval 数据，不缓存 Runtime-local Evidence。

------

# 2. 当前 WP 真实实现

WP3 最终落地两条真实生产链。

第一条：

```text
Authenticated Retrieval
        ↓
Principal.authz_domain_id
        ↓
CachedRetrievalExecutionService
        ↓
Redis Cache-Aside
        ├─ HIT → restore safe projection
        └─ MISS
              ↓
      RetrievalExecutionService
              ↓
       Dense + BM25 + RRF
              ↓
        safe cache projection
              ↓
            Redis
```

第二条：

```text
Authenticated HTTP Request
        ↓
Principal
        ↓
RedisTokenBucketRateLimiter
        ↓
Redis TIME + Lua
        ↓
ALLOW / 429 / 503
```

Redis Client 是 Application Scope，并通过 `redis.asyncio` 工作；没有 Per-request Redis Client。

------

# 3. Redis 在系统里到底是什么角色

WP3 一个非常重要的设计：

```text
Redis
!=
Knowledge Authority
!=
Retrieval Authority
!=
Runtime State Authority
```

Redis 在这里仅承担：

```text
Cache Acceleration
+
Traffic Governance
```

Cache Disabled、MISS、坏数据、Redis 故障时，系统仍然回到原来的：

```text
RetrievalExecutionService
```

继续执行：

```text
Dense
BM25
RRF
Materialization
Context Selection
```

所以即使：

```text
DEL all Redis keys
```

理论上系统只是变慢，不应该变错。Final Review 已确认这一点。

------

# 4. 为什么使用 Cache-Aside

当前模式：

```text
Application
    ↓
GET Cache
    ↓
HIT?
 ┌──┴──┐
YES   NO
 ↓     ↓
Return Origin Retrieval
        ↓
      SET Cache
        ↓
      Return
```

优点是：

> Redis 永远只是副本，真实 Retrieval 逻辑仍掌握正确性。

如果 Redis Down：

```text
Cache
→ bypass
→ Origin
```

不需要维护：

```text
Redis ↔ Retrieval Store
```

的双写一致性。

所以这一模式很适合：

> RAG Query Result 这种可重新计算的数据。

------

# 5. 为什么不能缓存整个 RetrievalExecutionResult

这是 WP3 最关键的设计之一。

源码审计后把 `RetrievalExecutionResult` 分成四类。

## A. 可以缓存

只包括成功 Retrieval 中可跨请求复用的确定性结果：

```text
rewritten_query_digest
final chunks
chunk text
score
stable SourceMetadata
RetrievalProvenance
display citation metadata
```

## B. 当前执行生成的 Runtime Identity

例如：

```text
retrieval_id
citation_id
context_block_id
status
```

Cache HIT 时必须为当前 Request 重新生成。

## C. Runtime Evidence

例如：

```text
stage_records
budget_usage
started_at
completed_at
duration_ms
span
activity
evaluation capture
```

这些属于当前 Invocation，不能从缓存复用。

## D. Execution-local State

例如：

```text
error
cancel state
timeout state
detached worker
event sequence
timestamp
RunContext
Principal
```

完全不能跨请求缓存。

因此：

```text
pickle(result)
repr(result)
asdict(result)
```

都不是安全方案。

------

# 6. Cached Retrieval Projection

最终建立：

```text
RetrievalCacheCodec
```

作为：

```text
Retrieval Result
↔
Cached Projection
```

唯一转换 Owner。

缓存 Schema：

```text
cached-retrieval-result.v1
```

Redis Envelope 当前是：

```text
schema = 2
```

同时加入：

```text
payload_digest
```

用于检测缓存内容被异常修改。

如果：

```text
unknown schema
unsupported projection version
malformed JSON
payload digest mismatch
```

统一视为：

```text
MISS
→ Origin
```

而不是信任 Redis 数据。

------

# 7. 为什么 Cache HIT 不能直接复用旧 Runtime Event

假设请求 A 做过 Retrieval：

```text
retrieval_id = R1
event_id = E1
timestamp = T1
```

请求 B 命中缓存。

错误做法：

```text
把 R1 / E1 / T1
连同结果一起返回
```

这会把：

> 请求 A 的 Runtime Evidence

伪装成：

> 请求 B 的 Runtime Evidence。

当前实现的语义是：

```text
Cache HIT
=
当前 Request 的一次新的 Retrieval Invocation
```

所以 HIT 会：

```text
生成新的 retrieval_id
重新生成 citation binding
重新发布 RETRIEVAL_STARTED
重新发布 stage/completed event
重新生成 timing/span/activity
```

Journal sequence 和 event identity 仍由当前 Runtime 生成。

------

# 8. Cache HIT 的 Budget 怎么算

Cache HIT 并不是：

```text
Retrieval 没发生
```

当前请求仍然发起了一次 Retrieval Call。

所以：

```text
retrieval_calls = 1
```

但因为没有真的执行：

```text
embedding
vector retrieval
BM25
RRF
document materialization
context materialization
```

对应 Usage：

```text
= 0
```

这比两种错误方案都合理。

错误方案 A：

```text
Cache HIT
→ 完全不算 Retrieval Call
```

会绕过 Runtime Budget Contract。

错误方案 B：

```text
Cache HIT
→ 假装完整执行过 Dense/BM25/RRF
```

会伪造资源消耗。

Final Review 已确认当前 Budget Contract 保持正确。

------

# 9. Cache Key 为什么这么复杂

当前：

```text
rag:v1:
<authz sha256>:
<generation sha256>:
<policy sha256>:
<normalized-query sha256>
```

它解决四类错误复用。

## Authz Domain

```text
USER A
≠
USER B
```

即使 Query 相同，也不能共享私有结果。

------

## Index Generation

```text
Generation G1
→ cached
```

知识库升级：

```text
G2
```

以后自动 MISS。

------

## Policy Digest

例如：

```text
top_k = 5
```

和：

```text
top_k = 20
```

不能命中同一缓存。

------

## Query Digest

避免直接把：

```text
用户原始 Query
```

放进 Redis Key。

减少：

```text
PII
Prompt
Sensitive Text
```

通过 Redis inspection 泄漏。

------

# 10. 为什么 Cache Key 必须包含 Principal Authz Domain

假设：

```text
USER A
```

能看到私有 Document X。

A 查询：

```text
Q
```

如果 Cache Key 只有：

```text
hash(Q)
```

那么：

```text
USER B
```

查询同样 Q：

```text
直接拿到 A 的 Result
```

这就是典型：

```text
Cross-user Cache Leak
```

所以生产路径真正使用：

```text
Principal.authz_domain_id
```

构建 Cache Identity。

没有 Principal 的内部调用：

```text
BYPASS
```

而不是偷偷使用：

```text
global
```

共享用户缓存。

------

# 11. 为什么 Cache Key 要有 Index Generation

RAG 索引发生变化以后：

```text
同 Query
```

答案可能不同。

如果 Key 没有：

```text
index_generation
```

旧缓存还会继续返回旧 Index Result。

现在：

```text
G1 + Q
→ key1
```

更新 Index：

```text
G2 + Q
→ key2
```

自然 MISS。

旧：

```text
G1
```

Key 等 TTL 自动过期。

不需要：

```text
SCAN rag:* → DEL
```

这种昂贵的主动全量清理。

------

# 12. Retrieval Policy Digest 为什么重要

影响 Retrieval Result 的不只是 Query。

Final Review 确认 Policy Identity 覆盖了：

```text
strategy
collection
top_k
rerank_top_k
filters / scope
minimum score
rewrite strategy
embedding capability
reranker capability
keyword retrieval capability
document/context limits
RRF k/profile
provenance identity
```

如果漏掉一个会影响结果的重要字段：

```text
Policy changed
```

但 Cache Key 没变：

```text
错误 HIT
```

这是 Cache Correctness，而不是单纯性能问题。

------

# 13. Final Review 发现的 Policy Digest Bug

Review 实际发现：

> 原来的 Baseline Policy Digest 漏掉了 Adapter Capability。

也就是说 Deployment Capability 变化时：

```text
embedding available
reranker available
keyword retrieval available
```

可能变化。

如果这些没进 Digest：

```text
新 Deployment
→ 复用旧能力组合下的 Cache
```

最终 Review 已把：

```text
embedding
reranker
keyword retrieval
```

三个能力位加入 Policy Identity。

这是一个很好的面试案例：

> 缓存 Key 的本质不是“怎么 Hash”，而是定义结果的完整 Identity。

------

# 14. TTL 为什么还需要 Jitter

如果 10 万个缓存：

```text
TTL = 10 min
```

并且在同一时间生成：

10 分钟后：

```text
同时过期
```

大量请求：

```text
Cache MISS
→ Origin Retrieval
```

形成：

```text
Cache Avalanche
```

所以加入：

```text
TTL Jitter
```

让不同 Key 的过期时间分散。

例如：

```text
600s ± bounded jitter
```

这样大规模失效不会集中到同一瞬间。

------

# 15. 为什么不缓存 Empty Result

WP3 明确：

```text
EMPTY
DEGRADED
FAILED
CANCELLED
TIMED_OUT
```

都不缓存。

只缓存：

```text
SUCCEEDED
```

原因是空结果可能只是：

```text
当前索引暂时没有内容
```

后续知识库更新后：

```text
本来应该查到
```

如果 Negative Cache 还没过期：

```text
继续返回 Empty
```

所以当前不做 Negative Cache。

------

# 16. Cache Fail Open

如果：

```text
Redis GET timeout
Redis SET timeout
Redis down
malformed cache
unsupported version
bridge timeout
```

缓存层：

```text
fail open
```

即：

```text
Origin Retrieval
```

继续执行。

Final Review 明确：

> Cache 是 acceleration，而不是 correctness authority。

例如：

```text
Redis Down
```

用户可能感知：

```text
更慢
```

但不应该：

```text
RAG 不工作
```

------

# 17. 为什么 Rate Limiter 不能 Fail Open

Rate Limiter 和 Cache 完全不同。

Cache：

```text
Redis Down
→ 我还可以直接算
```

Rate Limiter：

```text
Redis Down
→ 我不知道这个 Principal 还剩多少额度
```

如果这时：

```text
直接 Allow
```

多个 API 实例就可能完全失去流量控制。

因此：

```text
Limiter Redis unavailable
→ 503
```

不是：

```text
429
```

也不是：

```text
silent allow
```

Final Review 确认 Cache 和 Limiter 两种 Failure Policy 没被混在一起。

------

# 18. 429 和 503 有什么区别

## 429

表示：

```text
系统成功执行了限流判断
```

结论：

```text
你的额度确实耗尽
```

所以：

```text
429 Too Many Requests
```

并返回：

```text
Retry-After
```

------

## 503

表示：

```text
系统根本无法可靠执行限流判断
```

例如：

```text
Redis unavailable
```

所以：

```text
503 Service Unavailable
```

不是说用户超额，而是：

> 当前平台不能安全 Admission。

------

# 19. 为什么 Token Bucket 用 Lua

错误方案：

```text
GET tokens
↓
Python calculate
↓
SET tokens
```

假设：

```text
API Instance A
API Instance B
```

同时请求。

两边可能：

```text
GET tokens = 1
```

然后两边都：

```text
ALLOW
```

最终一个 Token 被消费两次。

当前：

```text
Redis Lua
```

一次完成：

```text
read
refill
consume
write
expire
```

整个脚本是一个原子操作。

因此多实例共享一个 Redis 时仍能得到统一额度。

------

# 20. Token Bucket 基本模型

核心状态：

```text
tokens
last_refill_time
```

假设：

```text
capacity = 10
refill = 2 token/s
```

初始：

```text
tokens = 10
```

连续 10 个请求后：

```text
tokens = 0
```

第 11 个：

```text
429
```

经过 1 秒：

```text
tokens += 2
```

又可以允许两个请求。

它同时允许：

```text
短时间 Burst
```

又控制长期平均请求速率。

------

# 21. 为什么 Lua 使用 Redis TIME

假设：

```text
API A clock = 12:00:00
API B clock = 11:59:58
```

如果两台机器自己计算 Refill：

可能对同一个 Token Bucket 得出不同结果。

现在 Lua 使用：

```text
Redis TIME
```

即：

```text
Shared Redis Time Authority
```

所有 API Instance 使用同一个时间源。

这减少分布式限流中的：

```text
Clock Skew
```

问题。

------

# 22. 为什么 Rate Limit 按 Principal，而不是 IP

IP Rate Limit 的问题：

```text
NAT
公司网络
家庭路由器
```

大量用户可能共用：

```text
一个 IP
```

反过来一个用户也可能：

```text
手机
WiFi
VPN
```

不停换 IP。

WP2 已经有：

```text
Server Verified Principal
```

所以 WP3 直接：

```text
Principal.authz_domain_id
→ limiter key
```

比 IP 更符合业务身份治理。

Pre-auth IP Limiter 当前不是完整 WAF，这也是明确 Accepted Limitation。

------

# 23. 为什么不用 Redis Distributed Lock

WP3 明确：

```text
DISTRIBUTED_LOCK = NO
```

Final Review 也确认没有：

```text
SET NX
Redlock
Fencing Token
Lease Renewal
```

原因不是：

> 不会做分布式锁。

而是：

> 当前根本没有一个真实 Critical Section 需要它。

Rate Limiter 的并发问题已经通过：

```text
Lua atomic operation
```

解决。

Cache 本身：

```text
允许多个请求同时回源
```

不会破坏正确性。

所以再加 Distributed Lock：

```text
复杂度 > 当前收益
```

这反而是更成熟的工程取舍。

------

# 24. Sync Retrieval + Async Redis 是怎么处理的

当前原始：

```text
RetrievalExecutionService
```

是同步 Runtime。

Redis：

```text
async
```

最终没有：

```text
asyncio.run()
```

散落到业务代码。

而是使用：

```text
SyncRedisBridge
```

由 Runtime Worker Thread：

```text
run_coroutine_threadsafe()
```

回到 Application Event Loop 执行 Redis I/O。

同时：

```text
Event Loop Thread
→ sync wait bridge
```

会直接拒绝，避免自锁。

Bridge 还有硬 Timeout。

------

# 25. Cache Deadline 怎么处理

Final Review 发现过一个问题：

> Cache Lookup 没显式受到 Run Deadline 约束。

这意味着：

```text
Run 已经快超时
```

却可能还：

```text
等 Redis
```

修复后：

```text
bridge timeout
=
min(
  bridge own timeout,
  invocation timeout,
  run remaining deadline
)
```

并且 Lookup 前先检查：

```text
Run active state
```

Run Deadline 已到：

```text
不再调用 adapter
不写 cache
返回现有 typed timeout
```

------

# 26. Corrupted Cache 为什么不能直接信 Redis

Redis 并不是 Security Authority。

Final Review 发现：

> 如果 Redis 中的 JSON 仍然合法，但内容被改写，之前可能继续命中。

例如：

```json
{
  "score": 0.7
}
```

被改成：

```json
{
  "score": 99
}
```

JSON 本身仍然合法。

因此最终 Envelope 加：

```text
payload_digest
```

读取时：

```text
recompute digest
↓
compare
```

不一致：

```text
MISS
→ Origin
```

注意这里 Digest 是：

> Corruption Detection。

不是把 Redis 提升为：

> Trusted Security Storage。

------

# 27. 为什么不把 Redis 加入 Readiness 的统一强依赖

因为 Redis 在两个功能上的语义不同。

Cache：

```text
optional acceleration
```

Cache Redis Down：

```text
可以回源
```

Limiter：

```text
Admission dependency
```

Limiter Redis Down：

```text
受保护业务请求 503
```

所以不能简单：

```text
Redis ping fail
→ 整个应用全部 unhealthy
```

需要根据具体 Capability 判断 Degraded / Unavailable。

------

# 28. 工程构建方法类问答

## Q1：为什么 Redis Cache 不能做 Authority？

因为缓存可以过期、丢失或整体删除，正确结果必须能够从 Origin 重新计算。

------

## Q2：为什么 Cache Key 不能只有 Query？

因为 Retrieval Result 还依赖用户权限、索引 Generation 和 Retrieval Policy。

------

## Q3：为什么 Index Generation 可以自然解决缓存失效？

新 Generation 会产生新 Cache Key，旧缓存不再命中，等待 TTL 清理即可。

------

## Q4：为什么 Policy Digest 很重要？

因为 top_k、reranker、filter、RRF 参数等变化都会改变 Result，如果 Key 不变就可能错误命中旧结果。

------

## Q5：Cache Redis 挂了为什么 Fail Open？

缓存只负责性能，回到 Origin 仍能得到正确结果。

------

## Q6：Limiter Redis 挂了为什么 Fail Closed？

Limiter 是 Admission Authority，无法判断额度时继续放行会失去跨实例流量控制。

------

## Q7：为什么 Rate Limit 用 Lua？

因为 Token Bucket 的读、Refill、Consume、Write 必须在 Redis 内原子完成。

------

## Q8：为什么用 Redis TIME？

避免多个 API 实例本地时钟漂移影响 Token Refill。

------

## Q9：为什么不用 Distributed Lock？

当前限流已经通过 Lua 原子性解决，Cache 重复回源也不破坏正确性，没有真实 Critical Section 需要锁。

------

## Q10：为什么不能缓存整个 Runtime Result？

因为 Result 中包含 request-local identity、event、budget、timing、trace 等不能跨请求复用的 Evidence。

------

## Q11：Cache HIT 是否算一次 Retrieval？

算。它是当前请求的一次 Retrieval Invocation，但没有执行 Origin Dense/BM25/RRF 计算。

------

## Q12：TTL Jitter 是解决什么的？

分散大量缓存同时过期造成的 Cache Avalanche。

------

# 29. 30 秒面试回答

我在 LocalAgent 里接入了 Redis，主要解决两类问题：RAG Cache 和分布式限流。RAG 使用 Cache-Aside，Redis 不是 Retrieval Authority，Cache MISS 或 Redis 故障时会直接回到原来的 Dense + BM25 + RRF。Cache Key 包含 Principal 的授权域、Index Generation、Retrieval Policy Digest 和 Query Digest，防止跨用户和跨索引版本错误命中。

限流使用 Redis Lua Token Bucket，以 Principal 为维度，Lua 内用 Redis TIME 原子完成 refill 和 consume。额度耗尽返回 429 和 Retry-After；Redis 故障时不是放行，而是 503 fail-closed。缓存则相反，Redis 故障会 fail-open 回源。

------

# 30. 2 分钟面试回答

我在 LocalAgent 的 HTTP 和 RAG 主链上接入了 Redis，但没有把 Redis 当业务 Authority，而是分别承担 Cache Acceleration 和 Traffic Admission。

RAG 用的是 Cache-Aside。生产 Retrieval 外面增加一个 CachedRetrievalExecutionService，原来的 RetrievalExecutionService 仍然负责 Dense、BM25、RRF 和 Context Selection。Cache Key 包含 Principal authz domain、Index Generation、Retrieval Policy Digest 和 Normalized Query Digest，所以用户权限变化、索引升级或者检索策略变化都会自然形成新的 Key。

比较重要的一点是我没有直接缓存整个 RetrievalExecutionResult。这个对象里有 retrieval ID、Runtime Event、Timing、Budget、Trace 等请求级状态，所以我单独定义了版本化 Cached Projection，只缓存 SUCCEEDED 的确定性 Chunk、Score、Source Metadata 和 Provenance。Cache HIT 时会重新生成本次请求自己的 Runtime Event 和 Timing Evidence，不复用旧请求。

Rate Limiter 则使用 Redis Lua Token Bucket。Lua 在 Redis 内通过 Redis TIME 原子完成状态读取、Token Refill、Consume 和写回，两个 API Instance 同时请求也不会发生 Python GET/SET 的竞态。超额返回 429 + Retry-After，而 Redis 不可用时返回 503，因为 Limiter 是 Admission Authority。

Cache Redis 故障则选择 fail-open 回到 Origin，因为 Cache 只是性能优化。这个 Failure Policy 的差异也是我认为 Redis 接入里比较重要的设计点。

------

# 31. 高频追问 + 简答

### Cache-Aside 和 Write-Through 最大区别是什么？

Cache-Aside 由应用在 MISS 时回源并写 Cache；Write-Through 通常要求写操作同时经过缓存层。本项目 Retrieval Result 是重新计算数据，因此使用 Cache-Aside。

### Redis 挂了 RAG 会不会挂？

不会，Cache 会 Fail Open 回到 Origin Retrieval。

### Redis 挂了 Rate Limiter 呢？

受保护 API 返回 503，因为无法安全判断额度。

### 为什么不是 429？

429 表示已经成功判断用户超限；Redis Down 是平台无法完成限流判断，所以是 503。

### Cache Key 为什么 Hash Principal？

既避免 Raw ID 暴露，又保持不同 Principal 的 Cache Namespace 隔离。

### 为什么不用 Redis DB 0/1 区分用户？

Logical DB 不是适合的 Multi-user Security Isolation 方案，本项目直接把 Authz Domain 放入 Key Identity。

### Cache HIT 会不会复用之前请求的 citation ID？

不会，会基于当前 Retrieval Invocation 重新生成绑定。

### Redis 能保证消息一致性吗？

本 WP Redis 不承担 Messaging；Kafka/Outbox 属于后续 WP。

------

# 32. Bad Case / Failure Scenario

## Bad Case 1：Cache Key 只有 Query

```text
USER A
Query Q
→ private result cached
```

USER B：

```text
Query Q
→ same cache key
→ data leak
```

正确：

```text
Authz Domain
+
Query Digest
```

------

## Bad Case 2：Index 更新但 Key 不变

```text
G1 result cached
```

Index：

```text
G2
```

Query 仍命中：

```text
G1 cache
```

正确：

```text
Generation
→ Cache Identity
```

------

## Bad Case 3：Python GET + SET Token Bucket

两个实例：

```text
A GET tokens=1
B GET tokens=1
```

两边都：

```text
ALLOW
```

正确：

```text
Redis Lua atomic operation
```

------

## Bad Case 4：Limiter Redis Down 后 Fail Open

Redis Down：

```text
Instance A allow
Instance B allow
Instance C allow
```

整个限流失效。

正确：

```text
503 Fail Closed
```

------

## Bad Case 5：把整个 Retrieval Result Pickle 到 Redis

下一请求命中后：

```text
旧 retrieval_id
旧 event_id
旧 budget
旧 timing
旧 trace
```

被重复使用。

正确：

```text
Versioned Safe Projection
```

------

## Bad Case 6：Cache Lookup 不受 Deadline 控制

Run 只剩：

```text
100ms
```

Redis：

```text
wait 5s
```

会破坏 Runtime Timeout Contract。

正确：

```text
wait timeout
=
min(local timeout, invocation timeout, run remaining)
```

------

# 33. Truth Boundary

当前真实实现：

```text
✅ redis-py asyncio
✅ application-scope Redis client
✅ bounded Redis connection pool

✅ Production RAG Cache-Aside
✅ Versioned Cache Projection
✅ Cache Payload Digest
✅ Authz Domain Isolation
✅ Index Generation Isolation
✅ Retrieval Policy Digest
✅ Query Digest

✅ TTL
✅ TTL Jitter
✅ Value Size Limit
✅ Corrupted Cache → MISS

✅ Cache Fail Open
✅ Empty/Degraded/Error not cached

✅ Redis Lua Token Bucket
✅ Redis TIME
✅ Principal-based Rate Limit
✅ Multi-instance Atomicity
✅ 429 + Retry-After
✅ Redis Limiter Failure → 503

✅ Real Redis Integration
✅ Redis 6380 test isolation
```

Final Review 已确认这些生产 Contract 成立。

尚未实现：

```text
❌ Redis Distributed Lock
❌ Negative Cache
❌ Cross-instance Single-flight
❌ High-concurrency RAG Benchmark
❌ Full Pre-auth WAF
```

------

# 34. Completion Boundary

最终：

```text
WP3_REVIEW_STATUS = PASS

REDIS_APPLICATION_OWNER_CONFIRMED = YES

RAG_CACHE_PRODUCTION_CONFIRMED = YES
RETRIEVAL_AUTHORITY_PRESERVED = YES

CACHE_PROJECTION_SAFE_CONFIRMED = YES
CACHE_RUNTIME_EVENT_CONTRACT_CONFIRMED = YES
CACHE_BUDGET_CONTRACT_CONFIRMED = YES

CACHE_AUTHZ_ISOLATION_CONFIRMED = YES
CACHE_INDEX_GENERATION_CONFIRMED = YES
CACHE_POLICY_IDENTITY_CONFIRMED = YES

CACHE_FAIL_OPEN_CONFIRMED = YES

RATE_LIMITER_ATOMICITY_CONFIRMED = YES
RATE_LIMITER_PRINCIPAL_IDENTITY_CONFIRMED = YES
RATE_LIMITER_FAIL_CLOSED_CONFIRMED = YES

DISTRIBUTED_LOCK_ABSENT_CONFIRMED = YES

REAL_REDIS_EVIDENCE_CONFIRMED = YES

P0 = 0
BLOCKING_P1 = 0

CAN_CLOSE_WP3 = YES
CAN_ENTER_WP4 = YES
```

Final Review：

```text
BUGS_FOUND = 4
BUGS_FIXED = 4
```

同样采用：

```text
Review
→ Find
→ Fix
→ Targeted Regression
```

没有重新跑整个 3000+ Test Suite。

------

# 35. Known Limitation / ACCEPTED_P1

当前明确接受：

```text
No Distributed Lock
No Negative Cache
No High-concurrency RAG Benchmark
No Cross-instance Single-flight
Pre-auth IP Limiter is not a full WAF
Legacy v1 Chroma without immutable generation bypasses cache
```

这些限制都不影响：

```text
Cache Correctness
+
Rate Limit Admission Correctness
```

其中：

```text
Legacy v1 Chroma
```

没有可靠 immutable generation 时选择：

```text
BYPASS
```

而不是冒险共享 Cache，是一个典型 Fail Closed / Safety-first Identity 设计。

------

# 36. 面试关键词

优先掌握：

```text
Redis

Cache-Aside
Cache Hit
Cache Miss

TTL
TTL Jitter
Cache Avalanche
Cache Penetration
Cache Breakdown

Cache Key
Cache Identity
Authorization Domain
Index Generation
Policy Digest
Query Digest

Safe Cache Projection
Schema Version
Payload Digest

Fail Open
Fail Closed

Token Bucket
Lua
Atomicity
Redis TIME

Rate Limiting
HTTP 429
Retry-After
HTTP 503

Connection Pool
Async Redis

Race Condition
Multi-instance

Cache Authority
Retrieval Authority

Cross-user Cache Isolation

Runtime Event Semantics
Budget Semantics
```

------

# 37. 本 WP 最值得掌握的 8 个问题

时间有限时优先吃透：

```text
1. 为什么 Redis Cache 不能成为 Retrieval Authority？

2. Cache-Aside 的完整读流程是什么？

3. 为什么 RAG Cache Key 必须包含 Authz Domain、Generation 和 Policy Digest？

4. 为什么不能直接缓存完整 RetrievalExecutionResult？

5. Cache HIT 时 Runtime Event 和 Budget 应该如何处理？

6. 为什么 Cache Redis Down 可以 Fail Open，而 Limiter Redis Down 要 Fail Closed？

7. Redis Lua Token Bucket 如何解决多个 API 实例之间的并发竞态？

8. 为什么当前没有使用 Redis Distributed Lock？
```

其中最值得记住的一句话是：

> **Redis 缓存解决的是“算得更快”，限流解决的是“能不能进来”；前者失败可以回源，后者失去 Authority 时必须拒绝。**