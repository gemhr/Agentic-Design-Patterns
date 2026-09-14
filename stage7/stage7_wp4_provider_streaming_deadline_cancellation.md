# Stage7-WP4 — Real Provider Streaming / Deadline / Cancellation

## 一、本 WP 解决了什么问题

WP4 解决的不是简单地把 HTTP 参数改成：

```text
stream=true
```

而是把原来的：

```text
同步 Provider HTTP
→ 等整个 Response
→ 一次性返回结果
```

升级成：

```text
异步 HTTP
→ 原生 SSE
→ Provider-neutral Delta
→ Runtime Incremental Acceptance
→ EventChannel
```

同时把：

```text
Deadline
Cancellation
Retry / Fallback
Tool Call Streaming
```

全部纳入同一套 Runtime 正确性边界。

现在真实 production chain 是：

```text
server.py::lifespan()
→ application-scoped RemoteLLMEngine
→ AgentRouter
→ ModelInvocationRouter
→ GeneratorModelAdapter.ainvoke()
→ RemoteLLMEngine.agenerate()/agenerate_native()
→ provider-neutral delta
→ OutputGate.stream_sink
→ RunEventEmitter
→ bounded EventChannel
```

------

# 二、名词 / 概念速览

### 异步 HTTP（Async HTTP）

Provider 请求通过 `httpx.AsyncClient` 发起，不再用同步 `requests` 阻塞 Runtime event loop。

### 服务端发送事件（Server-Sent Events, SSE）

Provider 通过一条长连接持续发送 `data:` event，实现增量输出。

### 增量输出（Incremental Streaming）

Model 生成一部分内容后立即向 Runtime 提交，而不是等待完整答案生成完再一次性返回。

### Provider-neutral Delta

把 OpenAI / DeepSeek wire JSON 转换成 Runtime 不依赖具体 Provider 的统一增量对象。

当前包括：

```text
TextDelta
ToolCallDelta
UsageDelta
Finish
```

### 输出开始屏障（Output-started Barrier）

一旦第一个输出已经被 Runtime 正式接受并可能对外可见，就禁止自动 Retry / Fallback。

### Fail-stop

已经输出部分内容后 Provider 出错，不偷偷切换另一个 Provider 继续拼接，而是直接失败并保留已发生事实。

### 绝对截止时间（Absolute Deadline）

Run 从一开始就拥有确定的 monotonic deadline，后续各层只能消费剩余 Budget，不能重新开始计时。

### Cancellation Propagation

Run 被取消以后，取消信号继续传到正在等待的 Provider HTTP request，并关闭本地 response/connection。

### Time-to-First-Delta

从请求开始到 Runtime 获得第一个可接受增量的时间。

### Backpressure

下游消费速度慢时，上游不能无限产生和缓存数据，需要有界传播压力。

### Streaming Tool Call

Provider 以多个 fragment 增量返回 Tool Call 名称或 arguments，Runtime 最后再聚合成完整调用。

------

# 三、为什么 `stream=true` 还不算真正的 Streaming

一个常见“伪 Streaming”实现：

```text
Provider stream=true

↓
程序内部把所有 chunk 收集起来

↓
拼成完整字符串

↓
Runtime 一次性返回
```

这种实现只能说：

> Provider wire 是流式的。

不能说：

> Runtime 是流式的。

WP4 Final Gate 专门验证：

```text
Provider 第二个 HTTP chunk 还没有发送

↓
第一个 Runtime OUTPUT_DELTA 已经可见
```

所以现在：

```ini
RUNTIME_INCREMENTAL_DELTA_REACHABLE = PASS
```

这是整个 WP 最重要的完成证据之一。

------

# 四、为什么 Provider Wire 不应该直接泄漏给 Runtime

假设 Runtime 直接处理：

```json
{
  "choices": [{
    "delta": {
      "content": "hello"
    }
  }]
}
```

那么 Runtime 会逐渐依赖：

```text
OpenAI schema
DeepSeek schema
某 Provider 的 finish_reason
某 Provider 的 tool_calls 格式
```

Provider Adapter 的正确职责是：

```text
Provider-specific SSE JSON
↓
normalize
↓
TextDelta / ToolCallDelta / UsageDelta / Finish
↓
Runtime
```

因此：

> Provider Adapter 拥有 Wire Protocol，Runtime 拥有 Agent execution semantics。

Final Gate 明确确认 Router 和 Runtime Event Layer 不解析 Provider SSE JSON。

------

# 五、为什么 SSE Parser 不能按 Network Chunk 解析 JSON

TCP / HTTP chunk 并不等于 SSE event。

例如 Provider 逻辑上发送：

```text
data: {"content":"hello"}
```

网络层可能拆成：

```text
chunk1:
data: {"cont

chunk2:
ent":"hello"}
```

也可能一个 network chunk 包含：

```text
data: A

data: B

data: C
```

所以错误实现是：

```python
async for chunk in response:
    json.loads(chunk)
```

正确流程是：

```text
raw bytes
→ SSE framing
→ 按空行切 event
→ 提取 data:
→ JSON parse
```

WP4 parser 已覆盖：

```text
fragmented data / JSON
multiple events per TCP chunk
comment / keepalive
[DONE]
malformed JSON
invalid UTF-8
```

协议错误会变成 typed `PROVIDER_PROTOCOL_ERROR`。

------

# 六、为什么 Deadline 必须是 Absolute Deadline

错误实现：

```text
Run timeout = 30 秒

第一次 provider read：
timeout = 30 秒

第二次 read：
又 timeout = 30 秒

第三次：
又 30 秒
```

这样一个所谓：

```text
30 秒 Run
```

理论上可能跑远远超过 30 秒。

这实际上是在不断“续租” timeout。

WP4 最终改成：

```text
absolute monotonic deadline
```

每次 read 都重新计算：

```text
remaining = deadline - monotonic_now
```

有效 Provider Budget：

```text
min(
    Run remaining,
    invocation cap,
    provider configured cap
)
```

因此：

> 下游 Timeout 只能越来越小，不能重新开始计时。

------

# 七、为什么使用 Monotonic Clock

Deadline 测的是：

```text
已经过去多少时间
```

不是：

```text
现在几点
```

Wall Clock 可能因为：

```text
NTP
系统时间修改
时区
管理员手动改时钟
```

发生跳变。

因此 Runtime Deadline 使用：

```text
monotonic clock
```

保证时间只向前推进。

------

# 八、Deadline 各层怎么传递

假设：

```text
Run remaining = 3s
Invocation cap = 10s
Provider timeout = 60s
```

最终 Provider 只能得到：

```text
3s
```

而不是 60 秒。

并且这个 bound 要继续作用于：

```text
connect
write
read
pool
stream next-read
```

Final Gate 已确认 HTTP 建连、Header 等待和每次 body read 都受绝对 deadline 控制。

------

# 九、Cancellation 和 Timeout 有什么不同

### Cancellation

表示：

```text
Runtime 主动不想继续了
```

例如：

```text
用户点击取消
客户端断开
Run 被取消
上层 orchestration 终止
```

### Deadline

表示：

```text
允许执行的时间已经耗尽
```

它不是人为主动 cancel。

### Provider Timeout

是：

```text
Provider invocation 自身达到 Provider / Invocation 限制
```

所以错误类型必须区分：

```text
Run Cancellation
Run Deadline Exceeded
Provider Timeout
Provider Connection Error
Provider Protocol Error
```

不能全部：

```text
MODEL_FAILED
```

WP4 Final Gate 保持 `RunDeadlineExceededError / DEADLINE_EXCEEDED` 与 Provider Timeout 的区分。

------

# 十、Cancellation 怎么真正打断 Provider HTTP

只做：

```python
run.cancelled = True
```

不够。

因为 AsyncClient 可能还在：

```text
await response read
```

正确链路：

```text
Runtime CancellationToken
↓
和 HTTP next-read 并发等待
↓
Cancellation wins
↓
cancel read task
↓
退出 response context
↓
关闭本地 HTTP stream
↓
停止接受后续 delta
```

WP4 当前就是这个语义。

但 Completion Truth 要诚实：

> LocalAgent 可以停止等待并关闭自己的连接，但无法保证第三方 Provider 的 GPU 计算或计费已经停止。

------

# 十一、为什么 Cancel 后不能继续接受 Delta

考虑：

```text
Runtime：
CANCELLED

Provider：
刚好又发送 token C
```

如果继续接受：

```text
A
B
cancel
C
D
```

用户看到的结果已经违反了 Runtime cancellation truth。

因此：

```text
cancel barrier 之前 accepted
→ 可以保留

cancel barrier 之后到达
→ 不允许 Runtime accepted
```

WP4 已验证 mid-stream cancellation 后后续 Provider bytes 不再成为 Runtime-visible delta。

------

# 十二、Output-started Barrier 是什么

这是 WP4 最重要的知识点。

假设 Provider A：

```text
输出："建议先检查数据库..."
```

用户已经看到。

随后连接断开。

如果 Router 自动 fallback：

```text
Provider B：
"对于这个问题，我们可以..."
```

用户看到：

```text
建议先检查数据库...
对于这个问题，我们可以...
```

内容被两个模型拼接。

所以需要：

```text
output_started barrier
```

规则：

```text
before first accepted output
→ retry / fallback possible

after first accepted output
→ retry / fallback forbidden
```

------

# 十三、为什么 Barrier 不能定义为“Provider 收到第一个 Token”

这是 Final Gate 实际纠正过的问题。

Provider 收到 Delta：

```text
Provider → TextDelta
```

并不一定意味着：

```text
Runtime 已经接受
```

例如 Runtime EventChannel publish 可能失败。

所以真正的 Barrier 必须在：

```text
Runtime acceptance
```

而不是：

```text
Provider chunk arrival
```

WP4 最终规则：

```text
OutputGate 成功 publish
or
部分 journal 已经不可撤销持久化

→ output_started=True
```

Provider Adapter 自己报告：

```text
“我已经输出了”
```

不能决定 Router barrier。

------

# 十四、Retry / Fallback 的正确边界

## 输出前

例如：

```text
connect reset
503
provider unavailable
transient timeout
```

而用户还没收到任何内容：

```text
Retry
or
Fallback
```

通常安全。

------

## 输出后

一旦：

```text
output_started=True
```

则：

```text
Retry = forbidden
Fallback = forbidden
```

因为无法撤回已输出内容。

WP4 最终由 `ModelInvocationRouter` 继续拥有 Retry / Fallback Policy，Provider Adapter 不自己重试。

------

# 十五、为什么 Mid-stream Failure 要 Fail-stop

假设：

```text
Provider A:
"数据库连接池应该设置..."

connection drop
```

这时：

```text
Retry Provider A
```

也可能生成不同内容。

Fallback B 更不可控。

因此正确语义是：

```text
partial output already visible
+
provider failed
→ stop
→ surface failure
```

而不是：

```text
换模型继续生成
```

这就是：

```text
fail-stop
```

Final Gate 已确认 connection drop、timeout、protocol error 等 mid-stream 场景都遵循该规则。

------

# 十六、Streaming Tool Call 为什么更难

普通文本 fragment：

```text
"hel"
"lo"
```

直接拼起来即可。

但 Tool Call arguments 可能是：

```text
fragment 1:
{"city":

fragment 2:
"Beijing",

fragment 3:
"days":3}
```

中间：

```text
{"city":
```

不是合法 JSON。

所以不能：

```text
每个 fragment
→ ToolInvocation
```

正确流程：

```text
ToolCallDelta
↓
按 call index/id 聚合
↓
name / arguments fragments 完整
↓
json.loads()
↓
NativeToolCall
↓
Typed Validation
↓
ToolInvocation
↓
Governance
```

WP4 保证 partial JSON 不会进入 Tool Runtime。

------

# 十七、Streaming Tool Call 还需要处理哪些边界

Final Gate 还要求处理：

```text
multiple tool calls
interleaved fragments
missing index
missing id
missing tool name
id/name conflict
malformed final JSON
incomplete arguments
```

这些情况都应：

```text
fail closed
```

而不是猜。

------

# 十八、为什么 AsyncClient 要 Application-scoped

错误：

```python
async def invoke():
    async with httpx.AsyncClient() as client:
        ...
```

每次 Model request 都重新：

```text
DNS
TCP
TLS
connection pool
```

高并发下浪费非常大。

WP4 使用：

```text
application-scoped RemoteLLMEngine
→ one AsyncClient
→ shared connection pool
```

并由 application lifecycle 统一关闭。

------

# 十九、为什么 Client Shutdown 也算正确性

如果程序退出时只是：

```text
engine.close()
```

但内部返回 coroutine：

```text
aclose()
```

却没人 await，会导致：

```text
unclosed client
pending task
connection leak
```

Final Gate 专门审计了：

```text
close / aclose
→ application bounded lifecycle helper
→ await coroutine
```

并验证 AsyncClient 最终 `is_closed=true`。

------

# 二十、Backpressure 为什么重要

假设：

```text
Provider: 100 token/s
Client: 10 token/s
```

如果 Runtime：

```text
provider
→ unbounded asyncio.Queue
```

积压越来越多：

```text
memory ↑
latency ↑
OOM risk ↑
```

WP4 没有新造 unbounded queue，而是：

```text
each delta
→ await Event Layer publish
→ existing bounded channel
```

让慢消费者自然反向限制 Producer。

------

# 二十一、为什么 OutputGate 不能缓存整个 Raw Output

Streaming 场景输出可能非常长。

如果同时：

```text
客户端收到 stream
Runtime 又把所有 chunk 存一个 list
```

那么：

```text
streaming
```

失去了内存优势。

Final Gate 实际发现并修掉过：

```text
OutputGate 无界累积 raw chunks
```

现在只维护：

```text
SHA-256 digest
+
character count
```

来校验最终 StepResult，不重复保存整份输出。

------

# 二十二、同步 Runtime 为什么还能保留

当前：

```text
AgentRouter
```

成熟 orchestration 仍有同步入口。

但它运行在：

```text
blocking worker
```

然后把 async Provider work 提交到：

```text
Runtime owner event loop
```

所以兼容 facade 可以保留。

关键是：

```text
sync facade
≠
第二套 sync Provider pipeline
```

Production Provider transport 已经统一是 async SSE。

------

# 二十三、工程方法类问答

## Q1：为什么不用 requests + iter_lines 实现 Streaming？

因为 Runtime 本身需要：

```text
cancellation
deadline
concurrency
incremental event delivery
```

同步 `requests` 会阻塞线程，取消和 Deadline 的传播都更困难。

Async HTTP 更适合 Agent Runtime。

------

## Q2：为什么 SSE Parser 要自己处理 Frame？

因为 TCP chunk 与 SSE event 没有一一对应关系。

必须先解析 SSE framing，再解析 JSON。

------

## Q3：为什么 Deadline 要向下传播？

否则上层虽然只有：

```text
3 秒 budget
```

底层 HTTP 仍可能等待：

```text
60 秒
```

Runtime Deadline 就失去意义。

------

## Q4：为什么每个 Stream Read 都重新计算 Deadline？

因为读取过程本身可能持续很久。

如果每次都重新给固定 30 秒，就会无限延长总执行时间。

------

## Q5：为什么取消 HTTP Connection 后还不能保证 Provider 停止计算？

HTTP client 只能控制本地 Connection。

请求可能已经到 Provider，Provider 是否继续 GPU inference 属于对方实现。

------

## Q6：Retry 和 Fallback 为什么只能发生在首输出之前？

因为首输出之后用户已经观察到了 Provider A 的结果。

换 Provider B 会制造不可撤销的拼接污染。

------

## Q7：为什么 output_started 要由 Runtime 判断？

因为只有 Runtime 知道某个 Delta 是否真正进入用户可见 / Journal 可见边界。

Provider Adapter 只知道网络层发生了什么。

------

## Q8：为什么 Tool Call 要等完整 JSON？

因为 ToolInvocation 是安全边界。

半截 JSON 不具备稳定、完整、可验证的参数语义。

------

## Q9：为什么 Provider Adapter 不直接写 Runtime Event？

因为 Provider Adapter 只拥有 Wire Normalization。

Runtime Event Authority 属于 Runtime Event Layer。

这样 Provider 与 Runtime 解耦。

------

## Q10：为什么普通最终文本支持 Streaming，但某个 native-tool first call 仍可能一次性发布？

因为 native-tool-enabled 的第一次调用可能最终生成 Tool Call。

如果提前把它当最终文本流给用户，后面才发现这是内部 Tool Planning 内容，就可能泄露本不应对外的中间结果。

因此当前保留安全缓冲边界。

------

# 二十四、30 秒面试总结

我们原来的 Provider 调用是同步非流式 HTTP，虽然 Runtime 上层支持事件，但 Model 结果基本还是生成完以后一次返回。我后来把 production Provider 改成 application-scoped `httpx.AsyncClient`，直接消费原生 SSE，并在 Adapter 层规范成统一的 TextDelta、ToolCallDelta、UsageDelta 和 Finish。

另外把 Run 的 absolute deadline 和 cancellation 一直传到在途 HTTP read。Cancel 会打断 read 并关闭本地 response，Deadline 也会限制 connect/read/write/pool 和每次 stream read。

最关键的是加了 output-started barrier：只有第一个 Delta 真正被 Runtime 接受以后才算输出开始；这个点之后禁止 retry/fallback，所以 mid-stream failure 会 fail-stop，不会偷偷换模型拼接答案。

------

# 二十五、2 分钟面试总结

我们之前 Model Provider 是基于同步 HTTP 的，Provider 请求会等完整 Response，Timeout 也是比较固定的。随着 Agent Runtime 支持 Streaming、Cancellation 和更严格 Deadline，这个 Provider 层就成了瓶颈。

所以我把 Remote Provider transport 改成了 application-scoped `httpx.AsyncClient`，通过原生 SSE 消费 Provider 输出。SSE parser 不假设 network chunk 就是一个 JSON，而是先按 SSE framing 重组 event，然后归一化成 Provider-neutral 的 TextDelta、ToolCallDelta、UsageDelta 和 Finish。

这些 Delta 会实时进入 Runtime OutputGate 和 EventChannel。我们专门验证过，在 Provider 第二个 chunk 还没发送时，第一个 Runtime OUTPUT_DELTA 已经可以看到，所以不是底层 stream、上层一次性 collect 的伪 Streaming。

Deadline 方面使用 RunContext 的 absolute monotonic deadline。每个 invocation 的 budget 是 Run remaining、invocation cap 和 Provider cap 的最小值，而且每次 stream read 都重新计算剩余时间。CancellationToken 会跟正在等待的 HTTP read 竞争，取消后关闭本地 response，并且 barrier 之后不再接受新 Delta。

另外一个关键设计是 output-started barrier。它不是 Provider 收到第一个 token 就触发，而是第一个 output 真正被 Runtime 接受以后才触发。在这之前允许根据 policy retry/fallback；一旦用户可能已经看到输出，就禁止 retry/fallback，mid-stream failure 直接 fail-stop。

Tool Call streaming 也会先聚合完整 arguments，JSON 验证成功后才构造 NativeToolCall，再进入原来的 Tool Validation 和 Governance，不让半截参数越过 Tool Runtime 安全边界。

------

# 二十六、高频追问

## 1. Streaming 最大的工程难点是什么？

不是 SSE parser 本身，而是：

```text
Streaming
+
Retry
+
Cancellation
+
Deadline
+
Runtime Event Truth
```

之间的正确性。

尤其是：

```text
输出后还能不能 retry
```

这个边界。

------

## 2. Mid-stream Provider 挂了怎么办？

如果已经存在 Runtime accepted output：

```text
fail-stop
```

不会自动 fallback。

因为已经无法撤销用户看到的内容。

------

## 3. 如果一个 Delta 到达的同时用户 Cancel 呢？

以 Runtime acceptance barrier 为准。

已经 accepted 的保留；Cancel canonical 后的新 Delta 不再接受。

------

## 4. Provider Streaming 能自动断点续传吗？

不能。

目前没有 resumable streaming 或 token-position resume。

这是明确 Accepted Limitation。

------

## 5. 真实 DeepSeek Streaming 测了吗？

没有。

WP4 使用 deterministic local real TCP/HTTP SSE 验证 Wire Protocol 和 production integration。

所以不能说：

> 已真实验证 DeepSeek streaming。

------

## 6. Cancel 是否能省掉 Provider 计费？

不能保证。

只能证明 LocalAgent 已停止等待并关闭本地连接。

------

# 二十七、Bad Case

## Bad Case 1：stream=true，但内部 collect 完再返回

```text
Provider streaming
→ list.append(delta)
→ join()
→ Runtime return
```

不是 Runtime Streaming。

------

## Bad Case 2：每个 Chunk 直接 json.loads

碰到 TCP fragmentation 就解析失败。

------

## Bad Case 3：每个 Read 都重新 timeout=30s

所谓 30 秒 Deadline 可以被无限延长。

------

## Bad Case 4：Provider 收到第一个 token 就 output_started=true

如果 Runtime publish 失败，Router 却以为用户已经看到输出，Barrier Authority 错位。

------

## Bad Case 5：Mid-stream failure 自动 fallback

用户最终看到两个 Provider 的答案拼在一起。

------

## Bad Case 6：Cancel 只设置 flag

Provider HTTP 仍然挂在 read 上，Runtime资源继续被占用。

------

## Bad Case 7：半截 Tool arguments 直接执行

```text
{"path":
```

直接进入 ToolInvocation。

严重破坏 Typed Validation / Governance 边界。

------

## Bad Case 8：每次 request 新 AsyncClient

连接池无法复用，TLS/连接成本高，资源管理复杂。

------

## Bad Case 9：OutputGate 保存全部 Raw Chunks

长输出可能造成不必要内存增长。

这个问题 Final Gate 实际发现并修复过。

------

# 二十八、本 WP 最重要的三个面试知识点

## 第一：Provider Streaming != Runtime Streaming

真正完成需要：

```text
Provider SSE
→ typed delta
→ Runtime incremental acceptance
→ EventChannel
```

------

## 第二：Retry/Fallback 的分界线是 Runtime Accepted Output

```text
Before output:
retry/fallback possible

After output:
fail-stop
```

------

## 第三：Deadline 必须是向下传播的 Absolute Budget

```text
Run deadline
→ Invocation
→ HTTP timeout
→ each stream read
```

不能各层自己重新开始倒计时。

------

# 二十九、Truth / Completion Boundary

## 已真实完成

### Async Provider HTTP

Production Remote Provider 使用：

```text
httpx.AsyncClient
```

### Application-scoped Client

共享 connection pool，由 application lifecycle 关闭。

### Native SSE

真实 HTTP chunked SSE。

### Wire Parser

支持：

```text
fragmented frames
multiple event/chunk
keepalive
DONE
malformed JSON
invalid UTF-8
```

### Provider-neutral Delta

```text
TextDelta
ToolCallDelta
UsageDelta
Finish
```

### Runtime Incremental Streaming

第一个 delta 在后续 HTTP chunk 到来前即可进入 Runtime Event Layer。

### Absolute Deadline Propagation

Run remaining budget 限制 Provider invocation。

### Stream Read Deadline

每次 read 重新计算 remaining budget。

### Cancellation Propagation

Cancellation 能打断在途 HTTP read。

### No Output After Cancel Barrier

Cancel 后不再接受新 Runtime delta。

### Output-started Barrier

定义在 Runtime acceptance。

### Pre-output Retry / Fallback

允许按已有 Router Policy 执行。

### Post-output Retry / Fallback

禁止。

### Mid-stream Fail-stop

断线/Timeout/Protocol Error 后不切 Provider 拼接。

### Streaming Tool Call Assembly

完整 JSON 后才能构建 `NativeToolCall`。

### Backpressure

逐 Delta await existing bounded EventChannel。

### Lifecycle

AsyncClient shutdown 已验证。

### Real HTTP SSE

使用本地真实 TCP/HTTP SSE Server 验证，不是纯 mock。

------

# 三十、尚未完成

## Remote Provider Guaranteed Cancellation

无法保证。

## Provider Billing Cancellation

无法保证。

## Resumable Streaming

未实现。

## Token-position Resume

未实现。

## Real DeepSeek Streaming Smoke

未执行。

## Native-tool First-selection Pure-text Full Incremental Streaming

存在一个 P2：

当 native-tool-enabled 的首次选择调用最后其实返回纯文本答案时，为避免提前泄漏潜在 Tool Planning 内容，该单一路径会确认 final 后一次发布，而不是全过程实时 streaming。

------

# 三十一、面试中不能夸大的地方

不要说：

> “Cancel 后 Provider GPU 一定停止。”

应该说：

> “Runtime 会取消本地 in-flight HTTP read 并关闭 response，但远端 Provider 是否停止计算属于 best-effort。”

不要说：

> “Streaming 可以透明断点恢复。”

应该说：

> “Mid-stream failure 当前是 fail-stop，没有实现 resumable streaming。”

不要说：

> “所有模型路径都已经完全逐 token 输出。”

应该说：

> “普通 final invocation、tool-result continuation 和 non-native Tool Provider 已支持 Runtime incremental streaming；native-tool-enabled 首次选择的纯文本特殊路径目前保留安全缓冲。”

------

# 三十二、一句话总结

> WP4 的本质不是“支持 SSE”，而是把 **Async Provider Transport + Runtime Incremental Acceptance + Absolute Deadline + Cancellation Propagation + Output-started Barrier + Fail-stop Retry Semantics + Streaming Tool Safety** 串成一个完整的 Agent Model Invocation Protocol。