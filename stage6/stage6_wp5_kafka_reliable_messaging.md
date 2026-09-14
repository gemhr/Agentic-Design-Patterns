# Stage6-WP5 — Kafka Reliable Messaging

## Kafka 可靠消息学习 / 面试总结

------

# 1. 名词 / 概念速览

**Apache Kafka**：本项目用于 Durable Job Event 的异步 Transport，不是 Job 或 Result 的业务 Authority。

**生产者（Producer）**：将 Outbox Event 发布到 Kafka Topic 的组件。

**消费者（Consumer）**：从 Kafka Topic 拉取 Event 并触发 Job 执行的组件。

**主题（Topic）**：Kafka 中消息的逻辑分类，本项目主 Topic 为 `evaluation.jobs.v1`。

**分区（Partition）**：Topic 的有序分片；同一个 Partition 内消息具有 Offset 顺序。

**消息键（Message Key）**：本项目固定为 `job_id`，用于让同一个 Job 的消息稳定映射到相同 Partition。

**消费者组（Consumer Group）**：多个 Consumer 以组的形式共同消费 Topic，本项目为 `localagent-evaluation-worker-v1`。

**偏移量（Offset）**：Consumer 在 Partition 中的消费进度。

**手动提交偏移量（Manual Offset Commit）**：业务处理完成后由 Worker 显式提交 Offset，而不是 Kafka Client 自动提交。

**自动提交（Auto Commit）**：Kafka Client 定时自动提交 Offset；本项目明确关闭。

**消费者去重（Consumer Dedup）**：使用 PostgreSQL 记录已经完成的业务 Event，防止 Kafka Redelivery 重复产生业务效果。

**至少一次投递（At-Least-Once）**：消息不会因为正常 Crash Window 静默丢失，但可能重复投递。

**幂等生产者（Idempotent Producer）**：Kafka Producer 通过 Broker 协议减少 Producer Retry 导致的重复写入，但不等于端到端 Exactly Once。

**Broker ACK**：Kafka Broker 对消息写入成功的确认。

**死信队列（Dead Letter Queue, DLQ）**：无法正常处理的永久 Poison Message 被发送到独立 Topic 保存。

**毒消息（Poison Message）**：Schema 错误、非法 Payload 或永久无法处理的消息。

**重新平衡（Rebalance）**：Consumer Group 成员变化时 Kafka 重新分配 Partition。

**工作租约（Worker Lease）**：Worker 对 RUNNING Job 的有限时间执行权。

**栅栏（Fencing）**：旧 Worker Lease 失效后，即使迟到返回，也不能覆盖新 Worker 的结果。

**运行尝试标识（Runtime Attempt ID）**：一次具体 Runtime Execution 的 Identity，与持久 Job Identity 分离。

**业务效果幂等（Business Effect Idempotency）**：消息重复到达也不会生成第二份 Result 或重新产生已提交的最终业务效果。

------

# 2. 当前 WP 真实实现

WP5 把 WP4 的 PostgreSQL Outbox 真正接入了 Kafka：

```text
HTTP
 ↓
PostgreSQL
 ├─ evaluation_jobs
 └─ outbox_events
 ↓
OutboxPublisherService
 ↓
KafkaEventSink
 ↓
evaluation.jobs.v1
 ↓
KafkaEvaluationWorker
 ↓
PostgreSQL Job Authority
 ↓
RuntimeEvaluationExecutor
 ↓
ChatService.run_coordinated_agent
 ↓
Result + Consumer Dedup Transaction
 ↓
PostgreSQL COMMIT
 ↓
Kafka Offset COMMIT
```

当前 Kafka Client 使用：

```text
confluent-kafka
```

Producer 和 Consumer 都已经接入真实生产路径；最终验证使用真实 Kafka + 真实 PostgreSQL。

------

# 3. Kafka 在当前架构里是什么角色

必须先记住：

```text
Kafka
!= Job Authority
!= Result Authority
!= Consumer Dedup Authority
```

当前 Authority 分工：

```text
Job
→ PostgreSQL

Outbox Intent
→ PostgreSQL

Final Result
→ PostgreSQL

Consumer Dedup
→ PostgreSQL

Kafka
→ Transport
```

Worker 收到 Kafka Event 后仍然重新读取 PostgreSQL 当前 Job State，而不是把 Kafka Message 当业务事实。

这和 WP4 的原则一致：

> Message 是 Trigger，Database State 才是 Authority。

------

# 4. Producer 为什么不能 `produce()` 后直接算成功

`confluent-kafka` 的：

```python
producer.produce(...)
```

本质上首先只是把消息加入 Producer 本地发送队列。

如果代码：

```text
produce()
↓
return success
↓
Outbox = PUBLISHED
```

此时进程 Crash，而 Broker 实际并没有收到消息：

```text
PostgreSQL:
PUBLISHED

Kafka:
message missing
```

消息就永久丢失。

当前实现：

```text
produce
↓
bounded flush / callback
↓
Broker ACK
↓
publish() returns success
↓
Outbox mark transaction
```

Broker Error、无 ACK、Timeout 都会失败。

------

# 5. Producer Idempotence 是什么

当前：

```text
enable.idempotence = true
acks = all
```

Idempotent Producer 主要解决：

```text
Producer send
↓
ACK response lost
↓
Producer retry
```

导致 Broker 侧重复写的问题。

Kafka 会利用 Producer Identity / Sequence 相关机制避免一部分 Producer Retry Duplicate。

但它不能解决：

```text
Kafka ACK success
↓
process crash
↓
PostgreSQL Outbox 尚未 Mark PUBLISHED
```

恢复后 Publisher 仍然会重新发送同一个 Event。

因此：

```text
Producer Idempotence
!= End-to-End Exactly Once
```

当前系统仍然明确是：

```text
AT_LEAST_ONCE
```

------

# 6. 为什么 Kafka Key 使用 job_id

当前：

```text
Kafka key = job_id
```

这样 Kafka 会对 Key 做稳定 Partition Mapping。

理论语义：

```text
Job A event 1
Job A event 2
Job A event 3
```

会倾向进入：

```text
same partition
```

因此可以利用 Partition 内顺序。

同时：

```text
job_id
```

是业务 Job Identity，

而：

```text
event_id
```

是一次业务 Event Identity。

两者不能混淆。

------

# 7. Kafka 的 At-Least-Once 到底是什么意思

当前链路里有多个可能重复的 Crash Window。

最典型：

```text
Kafka ACK success
↓
process crash
↓
Outbox PUBLISHED mark 尚未提交
```

恢复后：

```text
Outbox still PENDING
↓
Publisher republishes
```

所以同一个：

```text
event_id
```

可能被发布多次。

另一个：

```text
PostgreSQL business COMMIT
↓
process crash
↓
Kafka offset not committed
```

Kafka 会再次投递同一个 Message。

因此真实语义：

```text
可能重复
但不能丢
```

这是 At-Least-Once。

------

# 8. Consumer 为什么必须关闭 Auto Commit

当前 Consumer：

```text
enable.auto.commit = false

enable.auto.offset.store = false
```

如果打开 Auto Commit，可能出现：

```text
Consumer 收到 message
↓
Kafka 自动提交 Offset
↓
业务还没完成
↓
进程 Crash
```

Kafka 认为：

```text
message consumed
```

但 PostgreSQL：

```text
业务结果不存在
```

消息永久丢失。

所以 Offset Commit 必须由业务事务完成之后显式控制。

------

# 9. 最重要的 Offset 顺序

必须记住这一条：

```text
Consume
↓
Validate
↓
Business Processing
↓
PostgreSQL COMMIT
↓
Kafka Offset COMMIT
```

不能反过来：

```text
Consume
↓
Offset COMMIT
↓
Business Processing
```

因为如果 Offset 已经提交之后 Crash：

```text
Kafka 不会重投
+
数据库没有业务效果
```

等价于消息丢失。

------

# 10. 为什么 DB Commit 之后再 Commit Offset 仍然会重复

正确顺序虽然避免了丢消息，却会产生另一个 Crash Window：

```text
DB COMMIT success
↓
CRASH
↓
Offset COMMIT 没执行
```

Kafka：

```text
redeliver
```

这就是为什么：

> At-Least-Once 必须配合 Consumer Dedup / Idempotency。

------

# 11. Consumer Dedup 是怎么做的

当前 PostgreSQL：

```text
consumer_processed_events
```

唯一 Identity：

```text
(consumer_name, event_id)
```

它记录：

> 这个 Consumer 的这个 Event 已经产生 Durable Outcome。

Dedup Authority：

```text
PostgreSQL
```

而不是：

```text
Redis
in-memory set
Kafka offset
```

------

# 12. 为什么 Kafka Offset 不能代替 Consumer Dedup

Offset 表示：

```text
Transport Progress
```

Consumer Dedup 表示：

```text
Business Processing Evidence
```

Crash：

```text
DB business commit
↓
offset commit 前 crash
```

Kafka Offset 没前进：

```text
redelivery
```

但 PostgreSQL Dedup 已经存在：

```text
event already processed
```

Worker：

```text
不重复执行
↓
只补 Offset Commit
```

所以两者不是同一个问题。

------

# 13. Dedup 为什么必须和 Result 放在同一个事务

错误：

```text
INSERT dedup
COMMIT
↓
执行业务
```

Crash：

```text
dedup exists
business effect missing
```

消息 Redelivery：

```text
看到 dedup
→ skip
```

结果业务永久丢失。

当前成功 Finalization：

```text
BEGIN

Fenced Job Update

INSERT Result

INSERT Consumer Dedup

COMMIT
```

之后才：

```text
Kafka Offset Commit
```

这保证：

```text
dedup exists
```

就意味着相应 Durable Business Outcome 已经存在。

------

# 14. “Exactly-once-like Business Effect” 是什么意思

当前不能说：

```text
我们实现了 Kafka Exactly Once
```

真实情况：

```text
Kafka Message
可能重复

Evaluation Computation
Crash 后可能重复

Kafka DLQ
也可能重复
```

但是最终数据库：

```text
Result.job_id UNIQUE
+
Consumer Dedup
+
Worker Fencing
+
Conditional Finalization
```

保证同一 Job 不会重复产生两份最终 Durable Result。

所以更准确的说法是：

> 在 Kafka At-Least-Once Delivery 下，通过 PostgreSQL Dedup、Unique Result 和 Fenced Finalization，把最终业务效果收敛为幂等。

Final Review 明确：

```text
EXACTLY_ONCE_CLAIMED = NO
```

------

# 15. 为什么 Worker 还需要 Lease

WP4 Publisher 已经有 Lease。

WP5 又发现：

```text
Worker claims job
↓
Job = RUNNING
↓
Worker crashes
```

如果没有 Worker Lease：

```text
Job 永久 RUNNING
```

所以 WP5 给 Job 增加：

```text
worker_claim_owner
worker_claim_token
worker_claim_deadline
```

------

# 16. Worker Crash Recovery

正常：

```text
Worker A
→ Claim Job
→ RUNNING
```

如果 A Crash：

```text
lease expires
```

Worker B：

```text
Reclaim
→ new claim token
→ retry execution
```

Final Review 用真实 PostgreSQL 验证了：

```text
A lease expires
B reclaim
token changes
A late finalization rejected
B can finalize
```

------

# 17. 为什么 Worker 也需要 Fencing

只靠：

```text
worker_claim_owner
```

还不够。

场景：

```text
Worker A gets claim T1
↓
lease expires
↓
Worker B gets claim T2
↓
A late result returns
```

如果 A 还能 Finalize：

```text
old computation
→ overwrite current computation
```

所以 Finalization 条件包含：

```text
job_id
+
RUNNING
+
claim_owner
+
claim_token
+
claim_deadline > now()
```

旧 Token：

```text
T1
```

已经失效。

这就是 Fencing。

------

# 18. Job ID 和 Runtime run_id 为什么必须分离

实施阶段发现一个非常重要的问题：

原先如果：

```text
run_id = job_id
```

第一次 Worker Attempt 在 Runtime Journal 里已经留下：

```text
terminal / partial state
```

第二次 Crash Recovery 再使用同一个 `run_id`：

```text
可能撞到上一 Attempt 的 Runtime State
```

最终改成：

```text
job_id
=
Durable Business Identity
```

而：

```text
run_id
=
Fresh Runtime Attempt Identity
```

每次 Worker Attempt 都新生成 `run_id`。

这是一个非常好的面试点：

> 业务任务 Identity 和一次执行 Attempt Identity 往往不是同一个概念。

------

# 19. CANCELLED Job 收到 Kafka Event 怎么办

Kafka Event 可能早就已经发布：

```text
Job QUEUED event
```

随后用户：

```text
cancel
→ PostgreSQL status = CANCELLED
```

Worker 后来才收到 Event。

它必须：

```text
load PostgreSQL Job
↓
status = CANCELLED
↓
NO evaluation
↓
record durable CANCELLED_NOOP
↓
commit DB
↓
commit offset
```

不能：

```text
Kafka says queued
→ blindly execute
```

再次体现：

```text
Kafka = Trigger
PostgreSQL = Authority
```

------

# 20. 为什么 Kafka Message 还要和 PostgreSQL Outbox 对照

当前 Kafka Record 被当作：

```text
untrusted trigger
```

Worker 会校验：

```text
Kafka key = job_id

event_id
job_id
event type
aggregate type/id
schema version
payload
payload digest
```

然后与 PostgreSQL Outbox Intent 对照。

这可以阻止：

```text
伪造 Kafka Message
→ 随便触发某个 Job
```

也能识别 Schema / Identity 不一致。

------

# 21. 为什么不能要求 Outbox 必须是 PUBLISHED

这是实施过程中修过的高价值 Bug。

合法时序：

```text
Publisher
→ Kafka Broker ACK success
```

这时 Message 已经可能被 Worker 收到。

但是 Publisher 还没来得及：

```text
UPDATE outbox SET published...
```

所以 PostgreSQL 中：

```text
Outbox = PENDING
```

仍然是合法状态。

如果 Worker 写：

```text
only accept PUBLISHED outbox
```

会错误拒绝真正合法的 Event。

所以 Worker 要验证的是：

```text
Durable Outbox Intent exists
+
Identity matches
```

而不是强制要求 Publisher Mark 已完成。

------

# 22. Higher Offset Overtake 是什么问题

假设同一个 Partition：

```text
offset 10
offset 11
```

处理 `10` 时发生 Transient Failure。

如果 Worker：

```text
继续 poll
→ 成功处理 11
→ commit offset 11
```

Kafka 会认为：

```text
<= 11
都已经消费
```

那么 Offset 10 可能永久被越过。

实施阶段修复后：

```text
当前消息未完成
→ stop current consumer loop
→ no higher offset processing
```

Final Review 又确认失败会向 Supervisor 暴露，而不是假装 Worker 正常退出。

------

# 23. 为什么 Offset Commit 要检查 Partition Error

同步：

```python
consumer.commit(asynchronous=False)
```

返回，不等于：

> 每个 Partition 都一定提交成功。

当前会逐项检查：

```text
partition error
```

甚至：

```text
empty ACK
```

也不算成功。

这也是典型生产细节：

> API 调用成功返回和业务 Contract 成功不是一回事。

------

# 24. Long-running Evaluation 与 max.poll.interval

Evaluation 可能很慢。

如果：

```text
Evaluation duration
>
max.poll.interval.ms
```

Kafka 可能认为 Consumer 已死，触发 Rebalance。

当前 Final Review 给出的时间不变量：

```text
evaluation max = 3600s
lease = 3870s
max poll = 3900s
```

并要求：

```text
lease > evaluation + 30s

max poll >= lease + 30s
```

同时最终还真正加上：

```text
asyncio.timeout(max_evaluation_seconds)
```

不再只是配置层“算术约束”。

------

# 25. 为什么 Worker 不再叠一层完整 Evaluator Retry

如果：

```text
Model layer retry
Runtime retry
Worker retry whole evaluation
Kafka redelivery
```

全部叠加：

总耗时可能爆炸：

```text
超过 Lease
超过 max.poll.interval
```

然后造成：

```text
新 Worker Reclaim
+
旧 Worker 仍在重试
```

复杂度和竞态都会急剧增加。

当前 Worker 不再重试完整 Evaluator：

```text
超时 / infrastructure failure
→ message remains uncommitted
→ claim eventually expires
→ process restart / redelivery
```

------

# 26. DLQ 是解决什么问题的

不是所有失败都值得无限 Retry。

例如：

```text
malformed envelope
unsupported schema
Outbox intent mismatch
```

重复 100 次也不会自己变好。

这种消息属于：

```text
Poison Message
```

进入：

```text
evaluation.jobs.v1.dlq
```

------

# 27. DLQ 的正确顺序

必须：

```text
Publish DLQ
↓
Broker ACK
↓
Commit original offset
```

如果：

```text
Commit original offset
↓
DLQ publish fails
```

那么：

```text
原消息没了
DLQ 也没有
```

等价于永久丢消息。

当前 DLQ Publish 没有 ACK：

```text
original offset NOT committed
```

------

# 28. DLQ 为什么也可能重复

Crash Window：

```text
DLQ Broker ACK
↓
CRASH
↓
Original Offset not committed
```

Kafka Redelivery：

```text
再次 DLQ
```

所以：

```text
DLQ
也可能 At-Least-Once
```

当前没有声称 DLQ Exactly Once。

------

# 29. Rebalance 是什么

Consumer Group 中：

```text
Consumer 加入
Consumer 退出
Consumer Crash
Partition 数改变
```

都可能触发：

```text
Rebalance
```

Kafka 会重新分配 Partition。

当前没有建设复杂 Rebalance Framework，但 Final Review 确认：

```text
revoke / lost
不会 blanket commit

assign
会 reset generation-local state
```

最终业务正确性也不是完全依赖 Kafka Partition Ownership，而是由：

```text
PG Claim
Fencing
Unique Result
Consumer Dedup
```

兜底。

------

# 30. Multi-Worker 是怎么验证的

真实 Integration Test：

```text
2 partitions
2 consumers
same consumer group
```

确认两个 Consumer 都获得 Assignment。

同时业务侧：

```text
Result count = 1
evaluator.calls = 1
```

说明 Kafka Group Assignment 与 PostgreSQL 并发保护能够共同工作。

------

# 31. Producer / Consumer 为什么都不能阻塞 Event Loop

`confluent-kafka` 的部分核心 API 是同步边界。

当前 Producer / Offset Commit 等同步操作被放到工作线程执行。

Final Review 还修过一个细节：

原来 asyncio Cancellation 后：

```text
Python bridge cancelled
```

并不意味着：

```text
底层 librdkafka thread
立即消失
```

如果立刻释放 Lock / Close Producer：

可能出现：

```text
native Kafka call still running
+
producer closed concurrently
```

最终改成：

```text
先 drain 有界底层调用
再释放资源
```

------

# 32. 工程构建方法类问答

## Q1：Kafka 为什么采用 At-Least-Once？

因为业务 DB Transaction 和 Kafka Offset Commit 不在同一个原子事务里。正确设计优先保证不丢消息，再通过 Dedup/Idempotency处理重复。

## Q2：为什么 Offset 必须在 DB Commit 后提交？

否则 Offset 成功、DB 失败时，消息不会再投递，业务效果永久丢失。

## Q3：为什么 DB Commit 后仍然需要 Dedup？

DB Commit 成功但 Offset Commit 前 Crash 会产生 Kafka Redelivery。

## Q4：Consumer Dedup 为什么放 PostgreSQL？

因为它必须和最终业务结果拥有一致的 Durable Transaction Boundary。

## Q5：Kafka Producer 已开启 Idempotence，为什么仍然会重复？

因为 Idempotence 不能覆盖 Kafka ACK 与 PostgreSQL Outbox Mark 之间的 Crash Window。

## Q6：为什么 Worker 需要 Lease/Fencing？

RUNNING Worker 可能 Crash；Lease 允许恢复，Fencing 防止旧 Worker 晚到覆盖新 Worker。

## Q7：为什么 Kafka Event 不能作为 Job Authority？

Message 是历史 Trigger，Job 可能已经 CANCELLED、FAILED 或被 Reclaim，当前状态必须重新读 PostgreSQL。

## Q8：DLQ 为什么必须 ACK 后再提交原 Offset？

否则 DLQ Publish 失败时原消息会永久丢失。

## Q9：为什么不直接使用 Kafka Transaction 实现 PostgreSQL + Kafka Exactly Once？

当前 PostgreSQL Local Transaction 与 Kafka Transaction 并不存在一个共同的原子事务边界；项目使用 Transactional Outbox + Consumer Idempotency 解决这个问题。

## Q10：为什么不使用 Redis Distributed Lock 控制 Worker？

Job Claim Authority 已经在 PostgreSQL，通过 Conditional Update、Lease 和 Fencing 解决。

------

# 33. 30 秒面试回答

我在 LocalAgent 里把 Transactional Outbox 接到了真实 Kafka。Producer 使用 `confluent-kafka`，开启 Idempotent Producer 和 `acks=all`，只有 Broker ACK 后才把 Outbox 标为 Published。

Consumer 关闭 Auto Commit，处理顺序是消息校验、PostgreSQL 业务事务提交、最后同步提交 Kafka Offset。因为 DB Commit 后 Offset Commit 前 Crash 会 Redelivery，所以我用 PostgreSQL `(consumer_name,event_id)` 做 Consumer Dedup，并和 Result Finalization 放在同一个事务里。

Worker 本身还有 PostgreSQL Lease、Fresh Claim Token 和 Fencing，解决 RUNNING Worker Crash 后的 Reclaim，以及旧 Worker 迟到覆盖新结果的问题。整体明确是 At-Least-Once，不声称端到端 Exactly Once。

------

# 34. 2 分钟面试回答

这一阶段主要解决 Kafka At-Least-Once 下怎么保证最终业务结果不重复。

Producer 侧我没有把 `produce()` 入本地队列当成功，而是等待 Broker ACK；Outbox 只有 ACK 后才 Mark Published。即使 Kafka Producer 开了 Idempotence，ACK 后、PostgreSQL Mark 前 Crash 仍可能导致同一个 Event 重发，所以端到端还是 At-Least-Once。

Consumer 侧关闭了 Auto Commit 和 Auto Offset Store。消息消费后先校验 Kafka Event 和 PostgreSQL Outbox Intent，再 Claim Job、执行 Evaluation，并在一个 PostgreSQL Transaction 里完成 Fenced Job Finalization、唯一 Result 和 Consumer Dedup。只有数据库 Commit 后才同步 Commit Kafka Offset。

这样如果数据库已经成功，但 Offset 还没提交时进程 Crash，Kafka 会 Redeliver；新的 Consumer 查 PostgreSQL Dedup，发现 Event 已经处理，不会再次执行 Evaluation，只补 Offset Commit。

另外 RUNNING Job 不能只靠状态位，因为 Worker 可能 Crash，所以给 Worker 增加了 PostgreSQL 时间 Lease、Fresh Claim Token 和 Fencing。Lease 到期后其他 Worker 可以 Reclaim，而旧 Worker 即使迟到也无法 Finalize。

Poison Message 则进入 DLQ，必须 DLQ Broker ACK 后才提交原 Offset。所以系统总体不追求端到端 Exactly Once，而是在 At-Least-Once Transport 下保证最终 Durable Business Effect 幂等。

------

# 35. 高频追问 + 简答

### Kafka Producer Idempotence 和 Consumer Idempotency 是一回事吗？

不是。Producer Idempotence 主要减少 Producer Retry 的 Broker 重复写入；Consumer Idempotency 解决消息 Redelivery 导致的业务重复执行。

### Offset 是业务状态吗？

不是。Offset 只是 Kafka Transport Progress。

### Kafka 消息重复怎么办？

通过稳定 `event_id` + PostgreSQL Consumer Dedup + Unique Result + Fenced Finalization。

### 为什么 Dedup Key 不是 Partition + Offset？

当前业务 Identity 使用 `(consumer_name,event_id)`，因为同一业务 Event 可能在重新发布后出现不同 Transport Context，而 Event Identity 更符合业务去重。

### Worker Crash 后为什么 Evaluation 可能重复？

外部计算可能在 DB Finalization 前已经执行，但 Worker Crash 后没有 Durable 成功 Evidence，新 Worker只能安全重新执行。

### 那是不是 Exactly Once？

不是。外部 Computation 可以重复，但 Durable Final Result 被幂等保护。

### Poison Message 为什么不一直 Retry？

永久 Schema/协议错误不会因为等待而自愈，无限 Retry 只会阻塞 Partition。

### Kafka Down 会丢 Outbox 吗？

不会。Kafka Publish 失败时 Outbox 保持 PENDING，并按已有 Retry Contract 继续。

------

# 36. Bad Case / Failure Scenario

## Bad Case 1：Auto Commit

```text
consume
↓
auto commit offset
↓
business crashes
```

结果：

```text
message gone
business missing
```

------

## Bad Case 2：DB Commit 后没有 Dedup

```text
DB result committed
↓
crash
↓
offset not committed
↓
redelivery
↓
execute again
```

可能产生重复副作用。

------

## Bad Case 3：Dedup 先于业务提交

```text
insert dedup
commit
↓
business crashes
```

Redelivery：

```text
dedup hit
→ skip
```

业务永久丢失。

------

## Bad Case 4：Worker 无 Lease

```text
QUEUED → RUNNING
↓
worker crash
```

Job：

```text
RUNNING forever
```

------

## Bad Case 5：Lease 无 Fencing

```text
A lease expires
B reclaims
A returns late
```

A 仍可能覆盖 B。

------

## Bad Case 6：Higher Offset Overtake

```text
offset 10 fails
offset 11 succeeds
commit 11
```

Offset 10 被永久越过。

------

## Bad Case 7：要求 Outbox 必须 PUBLISHED

```text
Kafka ACK
↓
Worker receives
↓
PG mark not yet done
```

合法 Event 被错误拒绝。

------

## Bad Case 8：DLQ 前先提交 Offset

```text
commit original offset
↓
DLQ publish fails
```

Poison Message 永久消失。

------

# 37. Truth Boundary

当前真实实现：

```text
✅ confluent-kafka

✅ Real Kafka KRaft Integration

✅ KafkaEventSink

✅ enable.idempotence=true

✅ acks=all

✅ Broker ACK Confirmation

✅ job_id Message Key

✅ Outbox → Kafka

✅ Real Consumer Group

✅ Auto Commit Disabled

✅ Auto Offset Store Disabled

✅ Manual Synchronous Offset Commit

✅ Offset After PostgreSQL Commit

✅ Partition Commit Error Check

✅ PostgreSQL Consumer Dedup

✅ (consumer_name,event_id) Unique Identity

✅ Durable Result + Dedup Same Transaction

✅ Worker Lease

✅ PostgreSQL Time Authority

✅ Worker Fresh Claim Token

✅ Worker Fencing

✅ Worker Crash Recovery

✅ Fresh Runtime Attempt ID

✅ CANCELLED_NOOP

✅ Kafka Trigger ↔ PG Outbox Validation

✅ ACK-to-Mark PENDING Window

✅ DLQ

✅ DLQ ACK Before Original Offset Commit

✅ Multi-Worker Integration

✅ At-Least-Once
```

Final Review 已确认上述 Contract。

------

# 38. Completion Boundary

最终：

```text
WP5_REVIEW_STATUS = PASS

KAFKA_CLIENT_CONFIRMED = CONFLUENT_KAFKA

REAL_KAFKA_EVIDENCE_CONFIRMED = YES
REAL_POSTGRESQL_EVIDENCE_CONFIRMED = YES

PRODUCER_BROKER_ACK_CONFIRMED = YES
PRODUCER_IDEMPOTENCE_CONFIRMED = YES

OUTBOX_MARK_AFTER_ACK_CONFIRMED = YES
AT_LEAST_ONCE_CONFIRMED = YES

AUTO_COMMIT_DISABLED_CONFIRMED = YES
AUTO_OFFSET_STORE_DISABLED_CONFIRMED = YES
MANUAL_OFFSET_CONFIRMED = YES

OFFSET_AFTER_DB_COMMIT_CONFIRMED = YES
OFFSET_COMMIT_ERROR_CHECK_CONFIRMED = YES

POSTGRESQL_CONSUMER_DEDUP_CONFIRMED = YES
DEDUP_TRANSACTION_ORDER_CONFIRMED = YES

DUPLICATE_BUSINESS_EFFECT_BLOCKED = YES

WORKER_POSTGRESQL_AUTHORITY_CONFIRMED = YES
WORKER_LEASE_CONFIRMED = YES
WORKER_FENCING_CONFIRMED = YES
WORKER_CRASH_RECOVERY_CONFIRMED = YES

CANCELLED_JOB_NO_EXECUTION_CONFIRMED = YES

FRESH_RUNTIME_ATTEMPT_ID_CONFIRMED = YES

KAFKA_TRIGGER_OUTBOX_VALIDATION_CONFIRMED = YES
ACK_TO_MARK_PENDING_WINDOW_CONFIRMED = YES

DLQ_CONFIRMED = YES
DLQ_ACK_BEFORE_OFFSET_CONFIRMED = YES

MULTI_WORKER_CONFIRMED = YES

EXACTLY_ONCE_CLAIMED = NO

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0

CAN_CLOSE_WP5 = YES
CAN_ENTER_WP6 = YES
```

------

# 39. Known Limitation / ACCEPTED_P1

当前明确边界：

```text
No End-to-End Exactly Once

External Evaluation Computation
may repeat after crash/reclaim

Single-message Worker Pipeline

Infrastructure failure depends on
Supervisor restart / Kafka redelivery

No Kafka Streams

No Schema Registry

No Avro / Protobuf

No Retry Topic Hierarchy

No Complex Rebalance Framework

No Multi-region Kafka

No High-throughput Parallel Worker

Single-node KRaft
does not prove HA

Worker still reuses server.lifespan

No real remote-model E2E in this WP
```

这些属于明确 Scope / Production Limitation。

最终：

```text
ACCEPTED_P1 = 0
```

没有遗留 Blocking 缺陷。

------

# 40. Final Review 修掉的 5 个问题

这一部分非常适合用于面试讲“我真正遇到过什么坑”。

## 1. Kafka 原生线程与 asyncio Cancellation

问题：

```text
async bridge cancelled
但 native Kafka thread 仍然运行
```

如果立即 Close：

可能造成资源并发关闭。

修复：

```text
先 drain 有界 native operation
再释放 lock / close
```

------

## 2. Offset Commit 阻塞 Event Loop

问题：

```text
synchronous Kafka commit
```

直接跑在 Event Loop。

修复：

```text
offload to worker thread
```

同时保留 Partition Error 检查。

------

## 3. DLQ schema_version 可能泄露任意字符串

原来可能直接复制：

```text
schema_version
```

最终只允许安全、有界协议版本。

------

## 4. Worker Failure 被正常返回掩盖

原来未提交 Message 失败后：

```text
consumer closes
→ function returns normally
```

Supervisor 无法知道 Worker 异常。

最终：

```text
close
→ propagate safe exception
```

让 Supervisor Restart。

------

## 5. Evaluation Timeout 只有配置约束

原先虽然配置：

```text
max evaluation seconds
```

但实际 Evaluator 调用没有真正 Timeout。

最终增加：

```text
asyncio.timeout(...)
```

超时后：

```text
no finalization
no dedup
no offset commit
```

------

# 41. 面试关键词

重点掌握：

```text
Kafka

Producer
Consumer
Broker

Topic
Partition
Offset
Message Key

Consumer Group
Rebalance

Broker ACK
acks=all
Idempotent Producer

At-Least-Once

Manual Offset Commit
Auto Commit

Consumer Dedup

Business Idempotency

Transactional Outbox

Crash Window

DLQ
Poison Message

Worker Lease
Worker Claim
Fencing Token

PostgreSQL Time Authority

Redelivery

Offset Commit Ordering

Higher Offset Overtake

Runtime Attempt Identity

Job Identity

Durable Intent

Untrusted Trigger

Exactly-once-like Business Effect
```

------

# 42. WP4 → WP5 怎么串起来讲

WP4 解决：

```text
数据库已经产生业务状态
↓
如何保证“必须发消息”这件事不丢
```

方案：

```text
Transactional Outbox
```

WP5 解决：

```text
Outbox Event
↓
真正发进 Kafka
↓
Consumer 可能重复收到
↓
如何不重复产生业务效果
```

方案：

```text
Broker ACK

Manual Offset

PostgreSQL Dedup

Worker Lease/Fencing

Idempotent Finalization
```

完整链路：

```text
Business Transaction
↓
Transactional Outbox
↓
Kafka At-Least-Once
↓
Consumer Redelivery
↓
PostgreSQL Dedup
↓
Idempotent Business Effect
```

------

# 43. 本 WP 最值得掌握的 10 个问题

时间有限，优先吃透：

```text
1. 为什么 Kafka Producer produce() 返回不代表 Broker 已经收到？

2. Idempotent Producer 为什么不等于 Exactly Once？

3. 为什么 Consumer 必须关闭 Auto Commit？

4. 为什么 Offset 必须在 PostgreSQL Business Commit 后提交？

5. DB 已 Commit、Offset 未 Commit 时 Crash 怎么办？

6. Consumer Dedup 为什么要和业务 Result 放进同一个事务？

7. Worker RUNNING 后 Crash 为什么需要 Lease + Fencing？

8. 为什么 Kafka Event 是 Trigger，PostgreSQL Job 才是 Authority？

9. DLQ 为什么必须 Broker ACK 后才能提交原 Offset？

10. At-Least-Once 下怎么做到最终业务效果幂等？
```

最值得记住的一句话：

> **Kafka 的可靠性设计不是想办法让消息“绝对只来一次”，而是接受 At-Least-Once 和 Redelivery，然后用数据库事务、Consumer Dedup、Lease/Fencing 和业务幂等，让重复消息最终只能产生一次 Durable Business Effect。**