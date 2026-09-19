当前使用 GPT-5.6 Sol。

# Stage9-WP5 学习 / 面试总结

## Capacity Model + Load Evidence + Candidate SLO

WP5 解决的核心问题一句话可以概括为：

> **不再只说“Runtime 做了并发控制、连接池、SSE、Continuation，所以应该能扛”，而是把容量边界、真实负载结果和候选 SLO 用可复现证据明确下来。**

这一步和前几个 WP 最大的区别是：前面主要验证 **Contract Correctness**，WP5 开始验证 **这些 Contract 在并发压力下是否还能成立，以及瓶颈到底在哪里**。

最终 Gate 是：

```text
WP5_FINAL_GATE = PASS_WITH_C25_RUNTIME_LATENCY_SLO_FAIL

P0 = 0
P1 = 0
P2 = 1
```

唯一 P2 是 Tool scheduling load 没有实测；真正的 PostgreSQL-backed Runtime Run、SSE 和 Continuation 已经补齐负载证据。

------

# 1. WP5 最终真正做了什么

整个 WP5 可以理解成三件事：

```text
Capacity Model
+
Real Runtime Load Evidence
+
Candidate SLO Evaluation
```

第一层回答：

> 系统当前有哪些硬边界？

第二层回答：

> 在真实 Runtime Path 下测到什么程度？

第三层回答：

> 这些结果是否满足预先定义的工程目标？

最终不是只留下一个“性能不错”的结论，而是把：

```text
MEASURED
CALCULATED
SOURCE-DERIVED / INFERRED
NOT_TESTED
```

明确分开。

------

# 2. 为什么 Capacity Model 和 Load Test 都需要

只有 Capacity Model 不够。

比如源码告诉你：

```text
Tool concurrency = 16
```

这只能说明：

> 同时最多允许多少 Tool execution。

它不能说明：

```text
Tool throughput = 16 QPS
```

同样：

```text
DB pool = 5 + 5 overflow
```

也不能推导：

```text
DB capacity = 10 requests/s
```

这些只是 **Source-derived Bound**。

所以必须再通过真实 Runtime Path 测：

```text
latency
throughput
error rate
correctness
```

才能知道实际表现。

------

# 3. 为什么 Synthetic Benchmark 不够

Luna 第一版其实已经有：

```text
concurrency 1 / 5 / 10 / 25
100 requests each
0 errors
```

看起来数据很好。

但问题是它测的是：

```text
synthetic FastAPI endpoint
```

没有：

```text
PostgreSQL
Run lifecycle
Tool Snapshot
SSE
Continuation
```

所以它只能证明：

> Harness 能跑、HTTP transport 正常、percentile 算法工作。

不能证明：

> AgentCore Runtime 能扛这些并发。

Sol 最终明确把 synthetic 结果分类成：

```text
HARNESS / TRANSPORT ONLY
```

并另外补了真实 Runtime benchmark。

------

# 4. 这次真实暴露出的最大问题：Active Runs 无界

这是 WP5 最值得面试讲的真实 Bad Case。

在修复前：

```text
POST /api/v1/chat
↓
快速接受大量 Run
↓
后台 producer 不受全局 Active Run admission 限制
```

实测：

```text
c = 5
快速接受 100 Runs
↓
90 秒后
44 个 Run 没有 durable terminal
```

这说明：

> API 接收成功，不等于 Runtime 真正有能力完成这些 Run。

Sol 因此把它定为 P1。

------

# 5. 最终怎么修 Active Runs

没有引入新的复杂 Admission Framework。

而是直接复用：

```text
blocking_max_workers = 4
```

让：

```text
RunExecutionSupervisor
```

只允许：

```text
4 active producers
```

并且在：

```text
durable Run binding
```

之前等待 slot。

所以语义从：

```text
快速接受
↓
后台可能堆爆
↓
部分 Run 长时间无 terminal
```

改成：

```text
等待 admission
↓
拿到 producer slot
↓
durable bind Run
↓
开始执行
```

也就是说：

> **把“隐藏的后台失控”转换成“调用方可观察的排队延迟”。**

这是一个非常典型的生产系统取舍。

最终 Capacity Model 中 Active Runs 已变成 4。

------

# 6. 为什么宁愿让请求变慢，也不能先接受再说

因为：

```text
HTTP accepted
```

对于调用方意味着：

> 这个任务已经被系统可靠接收。

如果后台其实没有执行容量，但先给：

```text
200 / accepted
```

然后任务长期没有 terminal，

这属于：

> **Backpressure 被隐藏。**

更合理的是：

```text
Admission wait
```

让压力直接体现为：

```text
start latency 增长
```

至少：

```text
Accepted Run
```

后面是真的有 capacity 执行。

------

# 7. Runtime Run Start 的真实结果

最终测试环境是：

```text
单机
单 Uvicorn worker
本地 PostgreSQL
scripted backend
无 Remote Provider
```



真实 Run Start 结果：

| 并发 | 样本 | 成功率 | p95       | 吞吐      |
| ---- | ---- | ------ | --------- | --------- |
| 1    | 100  | 100%   | 136.44ms  | 11.46 RPS |
| 5    | 100  | 100%   | 697.16ms  | 11.53 RPS |
| 10   | 100  | 100%   | 1084.81ms | 11.37 RPS |
| 25   | 100  | 100%   | 2704.41ms | 11.05 RPS |

所有测试：

```text
Run ID unique
ownership exists
Tool Snapshot exists
5xx = 0
lost terminal = 0
```



------

# 8. 这组数据说明了什么

最明显的是：

```text
throughput ≈ 11 RPS
```

基本稳定。

但是随着并发增加：

```text
latency 持续增长
```

说明高并发请求不是让系统并行处理更多 Run，

而是：

```text
4-slot Active Run admission
↓
后续请求等待
```

所以 c=25 时：

```text
p95 = 2704ms
```

不是因为出现 correctness failure，

而是系统进入：

> **Queueing / Backpressure 阶段。**

最终报告也明确：

```text
SATURATION_REACHED = YES_LATENCY_AT_C25
CORRECTNESS_SATURATION_REACHED = NO
```



------

# 9. 性能 Saturation 和 Correctness Saturation 不一样

这是一个很值得记住的概念。

### Performance Saturation

表现为：

```text
p95 增长
queue 增长
throughput不再增长
```

但系统仍：

```text
不丢任务
不出错
不重复执行
```

### Correctness Saturation

表现为：

```text
Run loss
SSE gap
duplicate claim
terminal loss
```

当前 c=25：

```text
performance saturation = YES
correctness saturation = NO
```

这比简单说“系统到 25 并发不行”准确得多。

------

# 10. Candidate SLO 是什么

当前没有定义：

```text
Production SLA
```

只有：

```text
CANDIDATE_SLO_V1
```

它是：

> 工程回归目标，不是对外商业承诺。

例如：

```text
Runtime Run Start success >= 99%
Runtime Run Start p95 <= 2000 ms
SSE replay correctness = 100%
Continuation duplicate claim = 0
```

最终结果里：

```text
Run Start success → PASS
SSE replay correctness → PASS
Continuation claim safety → PASS

Run Start p95 at c25
→ FAIL
```



------

# 11. 为什么 Candidate SLO FAIL，WP5 还能 PASS

这是很好的面试问题。

因为 WP5 的目标不是：

> 把所有性能指标调到绿色。

目标是：

> 建立可信的容量证据体系。

实际结果证明：

```text
c25 p95 = 2704ms
```

而目标：

```text
<= 2000ms
```

所以系统诚实地输出：

```text
FAIL
```

并保留这个容量边界。

如果为了 Final Gate 把目标改成：

```text
3000ms
```

反而说明 SLO 没有意义。

所以：

```text
WP5 implementation
= PASS

Candidate SLO at c25
= FAIL
```

两者并不冲突。

------

# 12. 为什么不直接优化到 2 秒以内

因为当前已经知道：

```text
correctness = stable
```

而 c25 的问题主要是：

```text
4-slot admission queue
```

这属于容量设计取舍。

要进一步优化可能涉及：

```text
增加 active runs
增加 workers
调整 blocking executor
扩 DB capacity
多进程
```

这已经不是简单 Bug Fix。

WP5 的目标是发现并量化这个边界，不是为了面试把数字硬调漂亮。

------

# 13. SSE 的真实负载结果

SSE Replay：

```text
c=1 / 5 / 10 / 25
每档 100 samples
全部成功
```

p95：

```text
7.21ms
22.51ms
109.67ms
230.96ms
```

同时：

```text
replay_gap = 0
duplicate_logical_events = 0
terminal_loss = 0
```

Disconnect / Resume：

```text
20 / 20 successful
p95 = 13.50ms
accidental Run cancellation = 0
```



这意味着 WP2 的 resumable streaming 不只是单元测试通过，

而是已经有一定并发下的真实 correctness evidence。

------

# 14. 为什么 SSE Capacity 现在仍不能说“支持很多订阅”

因为当前：

```text
SSE subscription
```

没有显式全局上限。

而 Live Tail 使用：

```text
250ms PostgreSQL polling
```

所以可以做一个理论计算：

```text
poll_qps
≈ active_subscriptions / 0.25
```

比如：

```text
100 subscribers
≈ 400 DB poll reads / sec
```

但注意：

> 这是 CALCULATED，不是 MEASURED。

当前 load test 主要是 completed-run Replay，不是长期大量 idle live subscribers soak。

因此不能说：

> 支持 1000 SSE subscriptions。

当前报告也明确把 live SSE soak 列为 NOT_TESTED。

------

# 15. Continuation 的负载结果

Continuation：

```text
c=1 / 5 / 10 / 25
每档 100 items
```

结果：

```text
all claimed
duplicate = 0
remaining READY = 0
```

吞吐：

```text
416.70
358.46
356.24
354.07 claims/s
```

同时：

```text
expired PROCESSING
→ reap / reclaim

stale worker mutation
→ rejected
```



这验证的是：

> Continuation Scheduling Claim 在并发下没有 double claim。

它并不等于：

> 整个外部 Tool 副作用 exactly-once。

这两件事一定要分开讲。

------

# 16. 一个很重要的错误：Blocking Executor 卡 Event Loop

这次 Sol 还真实发现了另一个 P1。

原来：

```text
BoundedBlockingExecutor.submit()
```

在 Event Loop 上同步等待 admission。

如果 executor 满：

```text
Event Loop
↓
submit()
↓
等待 blocking slot
```

这会导致：

> Runtime Event Loop starvation / deadlock risk。

最终修改为：

```text
asyncio.to_thread(...)
```

把 blocking admission 移出 Event Loop，

然后：

```text
result_async()
```

异步取结果。

这是一个非常值得面试讲的 Production Bug。

------

# 17. 为什么 Blocking 操作不能在 Event Loop 上等待

因为 Event Loop 负责：

```text
HTTP
SSE
Task scheduling
async DB/IO continuation
```

如果它自己在等待：

```text
ThreadPool admission
```

就可能出现：

```text
线程池满
↓
Event Loop 等线程池 slot
↓
线程里的任务又等 Event Loop callback
↓
互相等待
```

即使没有形成严格 deadlock，

也可能导致严重 starvation。

所以：

> **Bounded Executor 本身是正确的，但 admission 也必须是 async-safe。**

------

# 18. 另一个真实 Bad Case：Client Feed Metric 名称错误

Sol Load Test 还发现：

```text
PostgreSQL Client Feed write
↓
emit metric
↓
metric 未注册
```

有可能导致：

```text
terminal projection 被中断
```

最终统一：

```text
runtime_client_event_feed_write_*
```

并补 metric descriptor。

这也是 Load Test 很有价值的地方：

> 很多问题单元测试不会暴露，只有真实整条 Path 跑起来才会出现。

------

# 19. 为什么 Load Test 不是只看性能

这次实际上发现的几个问题：

```text
Active Run unbounded
Blocking Executor Event Loop starvation
Metric emitter breaking terminal projection
```

都不只是：

```text
“慢”
```

其中两个直接影响：

```text
correctness / terminal delivery
```

所以 Production Load Test 应该同时观察：

```text
latency
throughput
errors
correctness invariants
```

不能只看 QPS。

------

# 20. Capacity Model 最终是什么样

当前几个主要边界：

| Resource          | 当前 Bound             | 说明                        |
| ----------------- | ---------------------- | --------------------------- |
| Active Runs       | 4                      | 实测 + Source-derived       |
| Model Calls       | 当前 10                | preset 8/10/12              |
| Tool Execution    | global 16              | 未 load test                |
| DB Connections    | 5 + 5 overflow         | 实际 Runtime Path 已经过 DB |
| HTTP Connections  | 100 / keepalive 20     | Pool Size，不是吞吐         |
| SSE               | 无显式订阅上限         | 250ms polling               |
| Continuation      | 无 global worker limit | Claim concurrency 已测      |
| Blocking Executor | 4 + 8 pending          | async-safe admission        |
| Redis             | 10                     | 本轮没压                    |



------

# 21. Owner / Truth / Evidence

这个 WP 的 Owner 思路跟之前不太一样。

这里最重要的是：

```text
Capacity Model
```

不能成为第二 Config Authority。

例如：

```text
ToolConcurrencyController
```

仍然决定真实 Tool concurrency。

Capacity Model 只是读取：

```text
global = 16
```

然后用于报告。

所以：

```text
Settings / Runtime Owners
= Capacity Truth

Capacity Report
= Source-derived observation

Benchmark
= Measured evidence

SLO Spec
= Engineering objective
```

这四个不要混。

------

# 22. Evidence Classification 必须会讲

### MEASURED

真正跑出来的：

```text
Runtime Run Start
SSE Replay / Resume
Continuation Claim
Synthetic HTTP
```

### CALCULATED

例如：

```text
SSE poll QPS
= subscriptions / 0.25
```

### SOURCE-DERIVED / INFERRED

例如：

```text
Tool global concurrency = 16
DB pool = 5 + 5
HTTP pool = 100 / 20
```

### NOT_TESTED

例如：

```text
remote LLM capacity
Tool load
multi-worker
long soak
autoscaling
```

面试里明确这么讲，会比“都支持”可信很多。

------

# 23. 为什么要绑定 Evidence Profile

Sol 还发现一个很严重的 Evaluator 问题。

原来：

```text
synthetic_start
```

的数据理论上可能被错误拿来满足：

```text
Runtime Run Start SLO
```

所以最终给 SLO 增加：

```text
required_evidence_profile
required_scenario
```

例如：

```text
PLATFORM_RUNTIME
+
runtime_run_start
```

Synthetic 数据：

```text
SYNTHETIC
```

就不能拿来满足 Runtime SLO。

这个修复被定义为 P0，因为：

> 一个会把错误证据判 PASS 的 SLO Evaluator，比没有 SLO 更危险。

------

# 24. PASS / FAIL / NOT_ENOUGH_EVIDENCE

Evaluator 最终不是只有：

```text
PASS
FAIL
```

而是：

```text
PASS
FAIL
NOT_ENOUGH_EVIDENCE
```

这三个状态语义：

```text
PASS
→ 有足够正确 Evidence，且满足目标

FAIL
→ 有足够正确 Evidence，但没有达到目标

NOT_ENOUGH_EVIDENCE
→ 根本没有足够证据下判断
```

不能把：

```text
没测
```

当成 PASS。

------

# 25. SLA 和 SLO 怎么区分

面试可以直接这样回答：

> SLA 是对外的服务承诺，通常涉及客户、赔偿或者商业责任；SLO 是内部工程目标。我这个项目目前没有 Production SLA，Stage9 建的是 Candidate SLO，用来约束回归和容量验证，所以单机 benchmark 结果不能被说成线上 SLA。

当前报告也明确：

```text
PRODUCTION_SLA_CLAIMED = NO
REMOTE_PROVIDER_CAPACITY_CLAIMED = NO
```



------

# 26. 什么是 Error Budget

例如：

```text
SLO success >= 99%
```

那么：

```text
Error Budget = 1%
```

也就是说：

在指定 Measurement Window 内，

系统允许：

```text
1%
```

失败。

但当前项目里的 Error Budget：

只是：

> Candidate Benchmark Window 下的工程概念。

不是：

```text
monthly production error budget
```

没有做完整 SRE Error Budget 平台。

------

# 27. 真实 Bad Case：Synthetic Evidence 被叫 api_start

Luna 第一版把 synthetic endpoint 命名成：

```text
api_start
```

容易让别人理解成：

```text
真实 /api/v1/chat Run Start
```

Sol 最终改成：

```text
synthetic_start
```

真实 Runtime 另设：

```text
runtime_run_start
```

这个修改看似小，但其实属于：

> Evidence Semantics Correctness。

因为性能测试最怕“数字是真的，但名字让人误解”。

------

# 28. 真实 Bad Case：接受 100 Run，但 44 个没有终态

这是本 WP 最值得记住的案例。

### 修复前

```text
100 accepted
↓
44 no durable terminal after 90s
```

### Root Cause

```text
Active Runs unbounded
```

### 修复

```text
RunExecutionSupervisor
→ 4 producer slots
```

### 修复后

```text
all accepted Runs
→ terminal eventually exists

c25:
latency ↑
correctness stable
```

这很好地体现：

> Backpressure 宁可变成 latency，也不能变成任务丢失。

------

# 29. 工程设计问题：为什么 Active Run Admission 放在 Durable Binding 前

如果先：

```text
create durable Run
```

再：

```text
wait capacity
```

那么数据库里会迅速积累：

```text
大量 accepted-but-not-runnable Run
```

当前策略：

```text
wait producer slot
↓
bind durable Run
↓
start execution
```

让：

> 已 durable accepted 的 Run 更接近真正获得执行能力。

这改变了 overload timing semantic，所以 Final Handoff 明确记录为 Breaking Change。

------

# 30. 面试高频题：你怎么做 Agent Runtime 的容量规划

可以回答：

> “我先把各资源 Owner 的真实边界抽出来，例如 Active Run、Model concurrency、Tool semaphore、DB pool、HTTP pool、Blocking Executor 和 SSE polling，不另外造一套 capacity config。然后把测试分成 synthetic harness evidence 和真正的 PLATFORM_RUNTIME evidence，后者实际经过 PostgreSQL、Run lifecycle、SSE 和 Continuation。最终看 p50/p95/p99、吞吐、错误率，同时还检查 Run loss、SSE gap、duplicate claim 这些 correctness invariant。”

------

# 31. 面试题：你现在系统支持多少并发

不要说：

> 25 并发没问题。

更准确：

> “我目前有单机、单 Uvicorn worker、local PostgreSQL、scripted backend 下到 25 并发的证据。Correctness 在这个范围内保持，但 Run Start p95 从 c=1 的约 136ms 增长到 c=25 的约 2.7s，并且超过 2s Candidate SLO。所以我只能说 correctness tested through 25，性能容量边界大概在 c=10 到 c=25 之间开始明显显现，不能外推成生产集群容量。”

------

# 32. 面试题：为什么吞吐一直只有 11 RPS

可以回答：

> “因为我后来给 Active Run 加了 4-slot admission。并发增加以后更多请求是在 admission 前排队，而不是增加并行 producer 数量，所以吞吐基本稳定在 11 RPS 左右，主要恶化的是 start latency。这个结果是预期的 backpressure，而不是继续无界创建后台 Run。”

------

# 33. 面试题：为什么不把 Active Run 从 4 改成 20

回答：

> “4 不是通过性能调优拍出来的新参数，它复用了当前 blocking worker capacity。Load Test 的目标先是关闭无界 Run 导致 terminal loss 的 P1。继续扩大 active Run 需要重新看 DB、executor、model 和 memory 的联合容量，所以我没有为了让 c25 SLO 变绿直接调大。”

------

# 34. 面试题：SLO 没达到为什么不优化

回答：

> “因为这轮目标是建立真实容量证据，不是把 benchmark 调成全绿。c25 下 correctness 没问题，但 p95 2.7s 超过 2s Candidate SLO，所以我保留 FAIL。要进一步优化应该作为下一轮 capacity tuning，而不是事后修改目标或者盲目增加并发参数。”

------

# 35. 面试题：你怎么证明 SSE 可恢复

现在可以回答：

> “我除了单测，还做了真实 Runtime load。Replay 在并发 1、5、10、25 下每档 100 次，replay gap、logical duplicate 和 terminal loss 都是 0。另外做了 20 次 disconnect/resume，全部可以从 cursor 继续，而且没有因为断开 subscription 去 cancel Run。”

这个回答现在有真实证据支撑。

------

# 36. 面试题：你怎么证明 Continuation 不会双 Claim

可以回答：

> “我对 PostgreSQL-backed Generic Continuation 做了并发 claim benchmark，在并发 1、5、10、25 下每档 100 个 READY continuation，duplicate claim 都是 0，同时还覆盖了 expired PROCESSING 的 reap/reclaim 和 stale worker mutation rejection。这里证明的是 scheduling claim single-winner，不把它夸大成外部副作用 exactly-once。”

------

# 37. 面试题：为什么不用平均延迟

因为平均数很容易被长尾掩盖。

生产 API 更关心：

```text
p50
p95
p99
max
```

例如当前：

```text
c25 p95 = 2704ms
```

这能直接反映：

> 大部分用户已经开始感受到 Admission Queue。

只看平均值会弱化这个问题。

------

# 38. 面试题：为什么 Remote LLM 不参加容量测试

回答：

> “我这轮测的是 Runtime 自身容量，如果引入 DeepSeek，结果会被 Provider latency、quota 和网络波动污染。所以主 benchmark 用 scripted backend，把 Provider 排除。Remote Provider 只适合另外做 provider-included smoke 或独立容量测试，不能混成 Runtime QPS。”

------

# 39. 面试题：怎么理解 Backpressure

当前项目最直观的例子就是：

### 错误

```text
压力过大
↓
继续 accept
↓
后台无限堆积
↓
Run 丢终态
```

### 正确

```text
压力过大
↓
Admission wait
↓
start latency increases
↓
correctness preserved
```

所以 Backpressure 的本质：

> **让上游感知下游容量不足，而不是把压力隐藏到系统内部。**

------

# 40. 如果真实面试再次问到“你的系统做过压测吗？”

### WP5 完成前

只能回答：

> “有并发和 semaphore，也有一些测试，但还没有形成正式 load evidence。”

### WP5 完成后

现在可以回答：

> “做过。我把 synthetic harness 和真实 Runtime evidence 分开。真实测试使用单机单 worker、本地 PostgreSQL 和 scripted backend，分别测了 Run Start、SSE Replay/Resume 和 Generic Continuation。Run Start 到 c25 仍然 100% correctness，但 p95 从 136ms 上升到 2.7s，超过 2s Candidate SLO。压测还实际暴露了无界 Active Run、Event Loop 上同步 executor admission、Client Feed metric projection 三个问题，其中无界 Run 曾导致 100 个 accepted Run 中 44 个 90 秒后没有 terminal，后来加了 4-slot admission，修复后 tested range 内 terminal loss 为 0。”

这是一个很强的项目事实回答，因为里面既有：

```text
问题
原因
修复
数据
限制
```

------

# 41. 如果被问“你的系统能扛多少 QPS”

最推荐回答：

> “我不会直接给一个生产 QPS，因为现在只有单机单 worker的 Runtime benchmark。当前 scripted backend 下 Run Start 吞吐稳定在约 11 RPS，测试到并发 25 时 correctness 仍然通过，但 p95 已到 2.7 秒，超过 2 秒 Candidate SLO。所以我的结论是当前 profile 下 c<=10 满足这个 SLO，c25 仍正确但已经进入 latency saturation；生产集群容量还没有证据。”

------

# 42. Known Limitations

当前明确没有测：

```text
Tool scheduling load
Remote LLM capacity
live SSE long soak
multi-worker
cluster scaling
autoscaling
multi-region
production traffic replay
RSS / memory long-term leak
```

DB Pool wait/timeout distribution 也没有单独 instrumentation，只通过真实 Run/SSE/Continuation Path 做了压力验证。

这些都不能在面试中说成已经做了。

------

# 43. WP5 最需要记住的 8 句话

1. **Capacity Bound 不等于 Throughput。**
2. **Synthetic HTTP Benchmark 不能代表 Agent Runtime Capacity。**
3. **Load Test 不只是看 QPS，还必须验证 correctness invariant。**
4. **Backpressure 应表现为可观察的等待/拒绝，而不是内部无限堆积。**
5. **Active Run 无界曾真实导致 accepted Run 没有 durable terminal。**
6. **c25 correctness 通过，但 p95 2.7s，Candidate SLO 真实 FAIL。**
7. **Candidate SLO FAIL 不代表 WP5 失败，反而说明 Evidence 系统没有掩盖问题。**
8. **单机、单 worker 的 11 RPS 绝不能外推成 Production SLA。**

推荐学习文件名：

```text
stage9_wp5_capacity_load_evidence_slo_learning.md
```

WP5 学习完成。下一步就不再是新的功能 WP，而是 **Stage9 Final Gate**：把 WP0～WP5 的 Contract、实现、测试、Accepted Limitation 和 Stage9 Completion Boundary 做一次最终收口。