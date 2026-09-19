当前使用 GPT-5.6 Sol。

进入 **Stage9-WP2 学习总结：Durable Client Event Feed + Resumable Streaming（持久化客户端事件流 + 可恢复流式传输）**。

这一 WP 的核心不是“实现 SSE 接口”，而是解决一个 Agent Runtime 进入真实后端环境后必然遇到的问题：

> **Agent 正在执行，但是客户端连接不是可靠的。Runtime 生命周期和用户连接生命周期必须解耦。**

------

# 1. WP2 解决的问题

传统 Agent：

```text
HTTP Request

↓

调用 LLM

↓

Streaming Response

↓

HTTP 断开

↓

任务结束
```

问题：

- 用户网络波动怎么办？
- 浏览器刷新怎么办？
- 手机切后台怎么办？
- 服务端多实例怎么办？
- 用户重新连接还能看到之前输出吗？
- 一个 Run 执行几十分钟，是否必须保持 HTTP 长连接？

所以 WP2 的目标：

把：

```text
Agent Run 生命周期
```

和：

```text
Client Connection 生命周期
```

拆开。

最终：

```
Run Execution
       |
       |
       v

Durable Event Store

       |
       |
       v

Client Subscription
```

------

# 2. 核心设计变化

之前：

```
Runtime
 |
 |
 HTTP Stream
 |
 |
 Client
```

现在：

```
Runtime
 |
 |
 Runtime Event
 |
 |
 PostgreSQL
 |
 |
 Client Feed
 |
 |
 SSE Connection
```

也就是说：

客户端不是 Runtime 的直接消费者。

客户端消费的是：

> Runtime 产生的持久化事件投影。

------

# 3. 为什么不能直接 Replay Runtime Journal

这里是一个很重要的面试点。

很多人第一反应：

> 已经有 Runtime Journal 了，直接 replay Journal 不行吗？

答案：

不适合直接暴露。

因为 Runtime Journal 是内部事实。

例如可能包含：

```text
Tool Invocation

Tool 参数

内部异常

Provider 信息

Execution Claim

Approval Digest
```

这些属于 Runtime 内部状态。

客户端需要的是：

```text
用户看到什么
```

所以增加：

## Client-safe Projection（客户端安全投影）

链路：

```
Runtime Event

↓

Projection

↓

Client Feed

↓

SSE
```

------

# 4. 两类 Event 的区别

## Runtime Event

面向：

Runtime 自己。

例如：

```
TOOL_STARTED

MODEL_CALL_STARTED

APPROVAL_CREATED

EXECUTION_CLAIMED
```

粒度更细。

------

## Client Event

面向：

用户。

例如：

```
RUN_STARTED

OUTPUT_DELTA

RUN_COMPLETED

ERROR
```

更稳定。

------

设计原则：

```
Runtime Truth

      ↓

Client Projection

      ↓

User View
```

只能单向。

不能：

```
Client Feed

      ↓

修改 Runtime State
```

否则 Client 层变成第二个 Runtime Authority。

这是面试经常追问的问题。

------

# 5. 数据模型

核心：

```text
client_delivery_events
```

类似：

```sql
id

run_id

cursor

event_type

payload

created_at
```

关键字段：

## run_id

属于哪个 Agent Run。

------

## cursor

客户端恢复位置。

例如：

```
run_001

cursor:

1
2
3
4
5
```

客户端收到：

```
cursor=3
```

然后断开。

重新连接：

```
after_cursor=3
```

读取：

```
4
5
...
```

------

# 6. 为什么 Cursor 用 Runtime Event Sequence

这里是一个架构取舍。

一种方案：

单独生成：

```
client_event_id
```

另一种：

复用：

```
runtime sequence
```

当前选择：

```
Runtime Event sequence
=
Client Cursor
```

原因：

避免：

```
Runtime Event

↓

Client Projection

↓

重新编号
```

造成两个序列系统。

但是要求：

这个 sequence 必须满足：

- 单调递增
- 稳定
- 唯一

------

# 7. Delivery Guarantee

WP2 明确：

不是 Exactly-once。

而是：

## At-least-once Delivery（至少一次投递）

含义：

系统保证：

> 事件不会因为客户端断线而永久丢失。

但是：

可能重复。

例如：

客户端收到：

```
cursor=10
```

但是 ACK 前断线。

重新连接：

```
after_cursor=9
```

服务器重新发送：

```
10
```

所以客户端需要去重。

Key：

```
(run_id, cursor)
```

------

# 8. 为什么不追求 Exactly-once

这是很重要的面试问题。

因为：

Exactly-once 通常需要：

```
Producer

↓

Broker

↓

Consumer

↓

ACK

↓

State Store
```

整个链路共同支持。

客户端网络：

不可控。

比如：

```
Server:

send event

↓

network timeout

↓

不知道 client 是否收到
```

服务器无法判断：

```
收到了吗？
```

所以真实系统通常选择：

```
At-least-once

+
Client Deduplication
```

------

# 9. SSE 为什么适合这里

当前使用：

## 服务端事件（Server-Sent Events, SSE）

而不是 WebSocket。

原因：

这个场景主要是：

```
Server
    |
    |
    v
Client
```

单向推送。

例如：

- Agent 输出
- 状态变化
- Tool Approval 等待

SSE 自带：

```
Last-Event-ID
```

天然支持：

```
断线恢复
```

------

# 10. SSE 请求链

当前：

## 创建 Run

```
POST /api/v1/chat


返回:

run_id

events_url
```

注意：

这里不是：

```
一直等待输出
```

而是：

创建任务。

------

## 订阅事件

```
GET

/api/v1/runs/{run_id}/events
```

流程：

```
Authorization

↓

查询 cursor

↓

Replay 历史事件

↓

进入 Live Polling
```

------

# 11. Replay + Live Tail

这是 WP2 最大的并发点。

流程：

```
Client Connect

↓

Replay:

cursor < current

↓

Live:

cursor >= current
```

问题：

Replay 和 Live 切换会不会丢？

例如：

```
12:00:00

读取历史到 cursor=10


12:00:01

Runtime 写入 cursor=11


12:00:02

进入 live
```

如果设计错误：

11 丢失。

------

当前方案：

持续：

```
read cursor > last_delivered_cursor
```

所以：

不会依赖某一个瞬间。

------

# 12. 为什么不用 Kafka 做实时推送

面试容易问：

> 既然有 Kafka，为什么不用 Kafka 推 SSE？

原因：

当前目标：

Durable Replay。

Kafka 可以：

```
transport

wake-up

async notification
```

但是：

Kafka 不应该成为：

```
Run Truth
```

当前：

```
PostgreSQL

=
事实存储
```

Kafka：

```
未来优化实时唤醒
```

例如：

```
Client Feed Updated

↓

Kafka Event

↓

SSE Worker wake up
```

但不是当前必须。

------

# 13. Disconnect 语义

这是 WP2 最大价值之一。

以前：

```
HTTP disconnect

↓

cancel task
```

现在：

## v1

```
Client disconnect

↓

close subscription

↓

Run continues
```

------

## Explicit Cancel

另外：

```
POST /cancel

↓

Authorization

↓

DurableRunControlService

↓

cancel Run
```

两者完全不同。

------

面试回答：

> 用户断网不应该等价于用户取消任务。网络连接只是观察通道，Run 生命周期应该由 Runtime 自己管理。

------

# 14. Cross Instance Replay

多实例：

```
Instance A

执行 Run

写 PostgreSQL


Client reconnect


Instance B

读取 PostgreSQL

恢复输出
```

不需要：

```
Instance A 的内存

EventChannel

Run Registry

Producer Task
```

这是非常重要的生产化能力。

------

# 15. Multi Subscriber

为什么不用 EventChannel？

因为：

EventChannel：

```
producer

↓

consumer
```

天然偏：

单消费者。

例如：

```
Client A 消费

Client B 看不到
```

而 Durable Feed：

数据库：

```
cursor=0

Client A

cursor=10

Client B
```

两个订阅者独立。

------

# 16. Terminal Event

一个 Run 最终：

```
COMPLETED

FAILED

CANCELLED
```

必须进入 Client Feed。

顺序：

```
Output Delta

↓

Terminal Event

↓

close subscription
```

不能：

```
Terminal

↓

Output
```

否则客户端状态混乱。

------

# 17. WP2 面试高频问题

------

## Q1：为什么 Runtime Journal 不能直接给用户？

回答：

> Journal 是 Runtime 内部事实，可能包含 Tool 参数、内部状态等敏感信息。客户端需要的是经过过滤后的稳定事件，所以中间增加 Client-safe Projection，保证 Runtime Truth 和 User View 分离。

------

## Q2：为什么断开连接不取消 Agent？

回答：

> 因为连接生命周期和任务生命周期不是一个概念。用户手机断网并不代表用户取消任务，所以 v1 中 disconnect 只关闭 subscription，显式 cancel 才进入 Runtime Cancel 流程。

------

## Q3：为什么不用 WebSocket？

回答：

> 当前主要是服务端向客户端推送 Agent 状态和输出，不需要复杂双向通信。SSE 自带 Last-Event-ID 语义，更适合这种事件恢复场景。

------

## Q4：如何保证重连不丢消息？

回答：

> 消息首先进入 PostgreSQL Client Feed，客户端携带 cursor 或 Last-Event-ID 重连时，从 cursor 后 replay，再进入 live polling，因此不依赖之前连接所在实例。

------

## Q5：为什么不是 Exactly-once？

回答：

> 网络层无法确认客户端是否真正收到消息，所以系统提供 At-least-once Delivery，并通过 run_id 和 cursor 做客户端去重，而不是声称 Exactly-once。

------

# 18. 这个 WP 对 JD 的价值

针对你刚才的京东物流 Agent JD，这个 WP 可以映射：

物流规划不是简单：

```
用户请求

↓

LLM

↓

返回答案
```

真实系统：

```
用户提交规划任务

↓

Agent 分析

↓

调用规划系统

↓

几十分钟计算

↓

用户断线

↓

重新打开页面

↓

继续查看结果
```

所以必须有：

- 长任务管理
- 状态持久化
- 流式进度
- 重连恢复
- 多实例访问

WP2 解决的就是这一层。

------

# 19. WP2 关键词速览

| 概念                 | 一句话                           |
| -------------------- | -------------------------------- |
| Durable Event Feed   | 持久化事件流，让客户端可恢复读取 |
| Projection           | 把内部事实转换成外部安全视图     |
| SSE                  | 服务端单向推送协议               |
| Cursor               | 客户端恢复位置                   |
| Last-Event-ID        | SSE 标准恢复机制                 |
| At-least-once        | 至少一次投递，允许重复           |
| Deduplication        | 客户端去重                       |
| Replay               | 根据历史事件恢复状态             |
| Live Tail            | 持续读取最新事件                 |
| Connection Lifecycle | 连接生命周期                     |
| Run Lifecycle        | 任务生命周期                     |

------

# 20. WP2 面试一句话总结

如果面试官问：

> 你这个流式输出怎么设计？

可以回答：

> 我没有把 Agent 执行和 HTTP 长连接绑定，而是让 Runtime 产生持久化事件，经过 Client-safe Projection 后写入 PostgreSQL Feed。客户端通过 SSE 订阅，断线后使用 cursor 或 Last-Event-ID 从 Feed replay，再继续读取最新事件。这样 Run 生命周期和连接生命周期解耦，也支持多实例下恢复。当前保证的是 At-least-once Delivery，通过 run_id 和 cursor 去重，没有声称 Exactly-once。

------

WP2 学习完成后，下一步进入 **Stage9-WP3：Tool Discovery + Run-level Tool Resolution Snapshot（工具发现 + 运行级工具解析快照）**。这也是对应你最开始那个 JD “100 个 Tool 怎么设计调度系统”的直接补强点。