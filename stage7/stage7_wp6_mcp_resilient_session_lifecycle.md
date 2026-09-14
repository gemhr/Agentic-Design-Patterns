# Stage7-WP6 — MCP Resilient Session Lifecycle

## 一、本 WP 到底解决了什么问题

Stage5-Phase9 已经解决了：

```text
MCP Tool
如何进入 LocalAgent 现有 Tool Runtime
```

也就是：

```text
MCP Provider
→ MCP Adapter
→ ToolRegistry
→ ToolGovernanceService
→ ToolExecutionService
```

WP6 没有重新做 MCP Integration。

WP6 真正解决的是：

> MCP Server 作为一个外部长期运行进程，如果出现 EOF、Process Exit、Read/Write Failure 或 Session 失效，LocalAgent 如何安全地重新建立 Session，同时保证 Tool Identity、Schema、Governance 和 Side-effect Safety 不被破坏。

最终 production chain：

```text
server.py::lifespan()
→ McpIntegrationComponent.start()
→ validated StdioMcpClient generation
→ build_mcp_registrations()
→ frozen ToolRegistry + ToolPolicyCatalog
→ AgentRouter
→ ToolGovernanceService / WP2 Approval + Claim
→ ToolExecutionService
→ McpBackedToolAdapter.invoke_once()
→ McpIntegrationComponent.session_for(server_id)
→ current validated StdioMcpClient
→ tools/call
```

MCP client 不再拥有自己的第二套 Runtime、Governance 或 Registry。

------

# 二、最终完成状态

最终 Gate：

```ini
WP6_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

P0_COUNT = 0
BLOCKING_P1_COUNT = 0
ACCEPTED_P1_COUNT = 0
P2_COUNT = 0

ARCHITECTURE_REOPEN_REQUIRED = NO

WP6_READY_FOR_LEARNING_OR_STAGE7_FINAL_GATE = YES
```

虽然结论写的是 `PASS_WITH_ACCEPTED_LIMITATIONS`，但这些限制都是 WP6 明确允许的能力边界，并没有记成 Accepted P1。

------

# 三、名词 / 概念速览

### 模型上下文协议（Model Context Protocol, MCP）

一种让 Agent / Model 通过标准协议访问外部 Tool Provider 的协议。

### MCP Session

LocalAgent 与一个 MCP Server 当前建立的有效协议会话。

### 会话生命周期（Session Lifecycle）

Session 从启动、可用、异常、重连到关闭的状态管理过程。

### McpIntegrationComponent

WP6 中 application-scoped 的唯一 MCP Session / Reconnect Owner。

### STARTING

MCP Server 正在启动、初始化、发现 Tool，还没有成为可用 Session。

### AVAILABLE

Session 已完成必要验证，可以被新的 MCP Tool Invocation 使用。

### DEGRADED

当前 Provider 不可安全使用，但 Component 仍存在，可进入 Reconnect。

### RECONNECTING

Lifecycle Owner 正在尝试重新建立、验证新的 Session。

### CLOSED

Application Shutdown 后的终态，之后不得再次 Reconnect。

### Session Generation

每一个通过完整验证的新 MCP Session 都拥有递增 generation，用来区分旧 Session 与新 Session。

### McpSessionHandle

绑定 `server_id + generation + client + provider_identity` 的不可变 Session Handle。

### 原子会话替换（Atomic Session Swap）

Reconnect candidate 完成全部验证之后，才一次性发布成新的 Current Session。

### 身份重新验证（Identity Revalidation）

Reconnect 后重新确认连接到的 MCP Server 仍然是原来允许的 Provider。

### Tool Identity Revalidation

确认之前冻结的 MCP Tool 在新 Session 中仍然存在且 Identity 没有变化。

### Schema Digest

Canonical Tool Input Schema 经过规范化后计算的 SHA-256，用来判断 Schema 是否发生改变。

### 有界指数退避（Bounded Exponential Backoff）

Reconnect 间隔逐步变长，但有最大值和最大尝试次数，避免无限忙循环。

### Jitter

给 Backoff 加少量随机扰动，防止多个实例同时 Reconnect。

### Singleflight / Single Reconnect Owner

同一个 MCP Server 同一时刻只允许一个 Reconnect Task。

### Read-only Replay

只读 MCP Tool 在严格条件下因 Transport Failure 失败后，允许在新 generation 上明确重放一次。

### Side-effect Replay Forbidden

有副作用的 MCP Tool 遇到断线后禁止自动重放。

### Frozen Registry

MCP Reconnect 不动态修改已经冻结的 LocalAgent ToolRegistry。

### Frozen Governance

Reconnect 不改变已有 Tool Policy / ToolExecutionSpec / Governance Authority。

------

# 四、为什么 MCP “重新连上”还不够

最简单的 Reconnect 逻辑可能是：

```text
session dead
→ spawn process
→ initialize success
→ continue
```

这不够。

因为一个新的 MCP Server 虽然：

```text
能启动
能 initialize
```

但它可能已经发生：

```text
Provider Identity 改变
Tool 被删除
Tool 被重命名
Schema 改变
```

如果 LocalAgent 直接接受新 Session：

```text
原来的 ToolRegistry / Governance Truth
```

就可能和：

```text
远端 Server Reality
```

不一致。

所以 WP6 的原则是：

> Reconnect 不是重新建立 TCP / stdio，而是重新建立信任。

新的 candidate 必须先完成：

```text
initialize
+
remote identity validation
+
tools/list
+
frozen Tool identity validation
+
schema digest validation
```

最后才允许发布为新的 Session Generation。

------

# 五、Lifecycle State Machine

当前状态：

```text
STARTING
AVAILABLE
DEGRADED
RECONNECTING
DISABLED
CLOSED
```

核心流程：

```text
STARTING
   ↓
AVAILABLE
   ↓
transport failure
   ↓
DEGRADED
   ↓
RECONNECTING
   ├── validated reconnect → AVAILABLE
   └── fail / incompatible / attempts exhausted → DEGRADED
```

Application Shutdown：

```text
→ CLOSED
```

`CLOSED` 是终态。

之后即使还有：

```text
broken callback
queued reconnect callback
process watcher event
```

也不能重新启动 MCP Server。

------

# 六、为什么 AVAILABLE 不能只看“进程还活着”

错误判断：

```text
subprocess alive
→ AVAILABLE
```

不够。

一个 MCP client 可能：

```text
Process 仍存在
但 stdio 已 broken
或者 client 已 closed
```

WP6 的 `acquire_session()` 会同时检查：

```text
Lifecycle State
Current Binding
client.closed
client.broken
```

因此底层已经失效的 Session 不会继续伪装成 AVAILABLE。

------

# 七、Session Generation 解决什么问题

例如：

```text
generation 1
→ server crash

reconnect

generation 2
```

如果没有 Generation，旧 Invocation 和新 Invocation 都可能只拿到：

```text
“当前 MCP client”
```

这样很容易发生：

```text
旧调用过程中 server 挂了
Component 换成新 client
旧调用突然在新 client 上继续
```

执行语义被偷偷改变。

WP6 使用：

```text
McpSessionHandle
=
server_id
+ generation
+ client
+ provider_identity
```

Handle 是 immutable。

所以：

```text
generation 1 Handle
```

永远还是：

```text
generation 1 client
```

不会因为 Reconnect 自动变成 Generation 2。

------

# 八、为什么 Replay 必须是一个明确的新 Attempt

错误方案：

```text
old handle
→ reconnect
→ secretly replace its client
→ continue
```

这样无法回答：

```text
这次 invocation 到底在哪个 Session 上执行的？
```

WP6 的 Read-only Replay 会明确记录：

```text
original_generation
new_generation
replay_count=1
```

这相当于告诉 Runtime：

> 原来的 Transport Attempt 失败了，我们明确做了一次新的 Replay Attempt。

而不是偷偷替换执行底座。

------

# 九、Atomic Session Swap 是什么

Reconnect 时正确顺序：

```text
创建 Candidate
↓
initialize
↓
initialized notification
↓
tools/list
↓
Identity Validation
↓
Tool Validation
↓
Schema Validation
↓
Candidate Health Check
↓
Publish New Generation
```

在所有验证完成之前：

```text
Candidate 不对 Tool Invocation 可见
```

如果：

```text
Identity mismatch
Schema mismatch
Required Tool missing
Candidate broken
Discovery cancelled
```

Candidate 会被关闭 / Reap，不会成为 Current Session。

------

# 十、为什么 Provider Identity 不能随便定义

Sol Final Gate 实际发现过一个很典型的问题：

Luna 最初把：

```text
serverInfo.version
```

也当成严格 Identity。

但 Phase9 原来的 Architecture 里：

```text
McpServerConfig.server_id
```

才是 Operator configured canonical server identity。

远端：

```text
serverInfo
```

属于 bounded untrusted metadata / provenance。

最终 WP6 使用：

```text
server_id
+
serverInfo.name
```

作为 Reconnect compatibility check。

而：

```text
serverInfo.version
```

只是 Observability Metadata。

所以：

```text
version change
```

不会导致 Reconnect 被错误拒绝。

这说明：

> Reconnect Safety 不能自行重新定义 Provider Identity Authority。

------

# 十一、为什么 Version 不适合做严格 Identity

软件升级后：

```text
serverInfo.name = github-mcp
version = 1.0 → 1.1
```

如果 version 是 Identity：

```text
合法升级
→ MCP permanent DEGRADED
```

就过于严格。

而如果：

```text
serverInfo.name
```

变成另一个 Server：

```text
github-mcp
→ unknown-server
```

风险就完全不同。

所以这次：

```text
name drift
→ fail closed

version drift
→ allowed + observable
```

这是 Reconnect Identity 的一个很好面试例子。

------

# 十二、Tool Identity Revalidation 为什么重要

假设初始 MCP Server 暴露：

```text
read_file
write_file
```

LocalAgent 已经把：

```text
write_file
```

注册进 frozen ToolRegistry。

Reconnect 后 Server 只剩：

```text
read_file
```

如果 Component 仍然 AVAILABLE：

LocalAgent Registry 会认为：

```text
write_file exists
```

但 Provider 根本没有。

所以：

```text
Required Frozen Tool Missing
→ Candidate Reject
→ DEGRADED
```

而不是部分继续运行。

------

# 十三、Extra Tool 为什么不能自动注册

Reconnect 后远端突然多出：

```text
delete_everything
```

如果 LocalAgent自动：

```text
tools/list
→ ToolRegistry.register()
```

就意味着：

> 外部 Server 可以在 Runtime 运行过程中改变 LocalAgent Safety Surface。

这违背 Stage5 Phase9 的 Authority。

所以 WP6 对 Extra Tool：

```text
ignore
```

不会：

```text
注册
生成新 Policy
更新 Adapter Schema
```

------

# 十四、Schema Digest 是干什么的

Tool 名字一样，不代表 Tool Contract 一样。

比如：

原 Schema：

```json
{
  "path": "string"
}
```

Reconnect 后变成：

```json
{
  "path": "string",
  "force": "boolean"
}
```

如果 LocalAgent Typed Validation 仍然按照旧 Schema，而远端执行新 Schema：

安全 Contract 已经不一致。

所以 WP6 对 Tool Input Schema 做：

```text
canonical JSON
→ UTF-8
→ sorted keys
→ compact separators
→ allow_nan=False
→ SHA-256
```

Reconnect 后必须：

```text
old digest == new digest
```

否则：

```text
MCP_TOOL_SCHEMA_MISMATCH
→ Candidate Reject
```

并且没有新造第二套 Schema Canonicalization，而是复用 Phase9 的 Contract。

------

# 十五、为什么不能 Reconnect 后热更新 Registry

假设 Schema 变了：

错误做法：

```text
Reconnect
→ detect new schema
→ update ToolRegistry
→ continue
```

这样意味着：

```text
Remote MCP Server
```

实际上获得了：

```text
修改 LocalAgent Runtime Contract
```

的权限。

这会绕过：

```text
ToolRegistry
ToolPolicyCatalog
Governance
Typed Validation
```

原来的冻结流程。

所以 WP6 选择：

```text
Schema changes
→ Fail Closed
→ Operator / Restart / Reconfiguration
```

而不是 Dynamic Hot Reload。

------

# 十六、Read-only Replay 为什么可以做

考虑一个：

```text
read_file
```

类型的 Tool。

执行：

```text
generation 1
→ call_tool
→ session disconnect
```

如果 LocalAgent 已经建立：

```text
generation 2
```

而 Tool 是严格：

```text
side_effect_kind = NONE
idempotency = READ_ONLY
```

那么重新执行一次通常不会改变外部世界。

所以第一版允许：

```text
最多 Replay 1 次
```

但必须满足：

```text
本地 frozen spec 允许
同一 invocation
未 cancel
Deadline 还有余量
新 generation 已完整验证
Replay count = 0
```

------

# 十七、为什么 Replay Eligibility 不能信任 remote annotation

MCP Server 可能返回：

```text
readOnlyHint=true
```

但这个 metadata 是远端提供的。

恶意 Server 完全可以把：

```text
delete_repository
```

标成：

```text
readOnly=true
```

如果 Lifecycle 层直接相信它：

```text
disconnect
→ automatically replay destructive operation
```

风险很高。

所以 WP6 Replay Classification 来自：

```text
LocalAgent frozen ToolExecutionSpec
```

必须同时：

```text
side_effect_kind = NONE
idempotency = READ_ONLY
```

Remote metadata 不能授予 Replay 权限。

------

# 十八、为什么 Read-only 也只 Replay 一次

即使是 Read-only，也不能：

```text
while failure:
    reconnect
    replay
```

否则可能造成：

```text
长时间卡住
请求风暴
隐藏真实 MCP 故障
```

WP6 的规则：

```text
第一次 Transport Failure
→ 等待更高 validated generation
→ replay once

第二次 failure
→ MCP_READ_ONLY_REPLAY_EXHAUSTED
→ fail closed
```

------

# 十九、为什么 Side-effect Tool 绝对不能 Replay

这是整个 WP6 最重要的安全点。

假设：

```text
MCP Tool：create_issue
```

执行：

```text
generation 1
→ tools/call
→ MCP Server 实际创建了 issue
→ stdio connection 断开
```

如果 Reconnect generation 2 后：

```text
Replay create_issue
```

就可能创建两个 Issue。

所以：

```text
Side-effect disconnect
→ NO REPLAY
```

而是接入 WP5：

```text
PREPARED
→ STARTED
→ tools/call
→ transport disconnect
→ UNKNOWN
```

------

# 二十、Reconnect 为什么不能解决 UNKNOWN

这是一个很容易答错的问题。

场景：

```text
generation 1

side-effect Tool
→ call
→ disconnect
→ UNKNOWN

generation 2
→ reconnect success
```

此时只证明：

```text
Transport restored
```

并不能证明：

```text
之前那个 operation 没执行
```

所以：

```text
Session generation 2 AVAILABLE
```

不能让：

```text
old UNKNOWN
→ retry
```

也不能：

```text
old UNKNOWN
→ NOT_COMMITTED
```

WP6 的真实测试确认：Reconnect 到 generation 2 后，旧 durable invocation 仍是 UNKNOWN，而且 Provider call counter 仍然是 1。

------

# 二十一、WP5 与 WP6 的关系

可以这样理解。

## WP6

回答：

> MCP Transport / Session 现在还能不能用？

状态：

```text
AVAILABLE
DEGRADED
RECONNECTING
```

## WP5

回答：

> 某一次已经开始的副作用到底有没有成功？

状态：

```text
PREPARED
STARTED
COMMITTED
UNKNOWN
```

两套 Truth 完全不同。

所以：

```text
Session AVAILABLE
```

不代表：

```text
old Tool invocation COMMITTED
```

也不代表：

```text
old Tool invocation NOT_COMMITTED
```

------

# 二十二、为什么 Reconnect 需要 Singleflight

可能同一时间出现：

```text
stdout EOF
process watcher detects exit
pending read fails
write fails
```

如果每个错误都：

```text
create_task(reconnect())
```

可能出现：

```text
4 errors
→ 4 MCP child processes
```

WP6 使用：

```text
每 server 一个 reconnect task
```

并且底层 Client `_break()` 会 at-most-once 收口 Transport Broken。

------

# 二十三、为什么还需要 Pending Reconnect Intent

Final Gate 实际抓出了一个很细的 Race：

```text
Reconnect Task
→ candidate generation 2 刚发布

generation 2 立即又 broken

但 generation 1 的 reconnect task 还没完全退出
```

如果 Component 只判断：

```text
“已经有 reconnect task”
```

就可能把这次新的 broken event 丢掉。

最后增加了：

```text
_pending_reconnects
```

记录：

> 当前 Reconnect Owner 完成以后，还需要再发起一次 Reconnect。

这样：

```text
singleflight
```

和：

```text
不能丢 reconnect intent
```

同时满足。

------

# 二十四、为什么 Reconnect 必须 Bounded

错误实现：

```python
while True:
    try_reconnect()
```

可能导致：

```text
Server 永久坏了
→ 无限 Spawn / CPU / Log
```

WP6 使用：

```text
bounded attempts
+
exponential backoff
+
bounded jitter
```

实现的默认策略会逐步增大等待时间，并限制最大 Delay 和最大 Attempts。

------

# 二十五、Deadline 怎么约束 Reconnect

一个 Tool Invocation 可能只有：

```text
500ms remaining
```

Session 恰好断开。

即使 Read-only Tool 有 Replay 权：

也不能：

```text
Reconnect 等 2 秒
→ 再 Replay
```

WP6 会持续使用：

```text
ToolAdapterContext.remaining_seconds()
```

约束：

```text
Initial Call
Wait for New Generation
Replay
```

Deadline 到期：

```text
No wait
No replay
Fail
```

------

# 二十六、Cancellation 怎么处理

Run / Tool Cancellation 发生后：

```text
停止本地 MCP Invocation Await
```

Client 可以 best-effort：

```text
notifications/cancelled
```

但不能声称：

```text
Remote MCP Server 一定停止了操作
```

Read-only：

```text
Cancel
→ no replay
```

Side-effect 如果已经跨过 External Boundary：

```text
Cancel
→ WP5 UNKNOWN
```

------

# 二十七、Shutdown 为什么特别容易出 Bug

Lifecycle 有很多 Background Task：

```text
reader
stderr
process watcher
reconnect
cleanup
```

如果关闭顺序不正确，Application 已经 Shutdown 后：

```text
late callback
→ reconnect()
→ spawn new MCP process
```

Final Gate 实际发现：

```text
queued pending reconnect callback
可能在 CLOSED 后创建新 task
```

最终：

```text
_schedule_reconnect()
```

增加 CLOSED Fail-closed Guard。

------

# 二十八、Shutdown 正确流程

当前：

```text
component.close()
```

会：

```text
_closed=True
↓
cancel reconnect/background tasks
↓
clear pending reconnect
↓
close current sessions
↓
close previously broken owned clients
```

`StdioMcpClient.close()` 继续：

```text
close stdin
→ bounded wait
→ terminate
→ kill if needed
→ reap child
→ cancel reader/stderr/process watcher
```

Shutdown 后测试确认：

```text
no reconnect task
no background task
no owned client
no later respawn
```

------

# 二十九、为什么要追踪 Broken Client

Final Gate 还发现：

```text
Broken Client
已经从 current binding 移走

但它的 cleanup task 又被 shutdown cancel
```

如果 Component 只关闭：

```text
current client
```

旧 Broken Child Process 可能泄漏。

所以最终 Component 还追踪：

```text
_owned_clients
```

Shutdown 时统一 Reap。

------

# 三十、真实 stdio MCP 测试证明了什么

WP6 没有只用：

```text
FakeMcpSession
```

它实际通过：

```text
asyncio.create_subprocess_exec
```

启动本地 Child Process，并按当前 Client 真正的 newline-delimited JSON-RPC Wire 走：

```text
initialize
notifications/initialized
tools/list
tools/call
```

同时真实制造：

```text
process exit
call 中途 disconnect
reconnect
shutdown
```

因此：

```ini
REAL_STDIO_MCP_INTEGRATION = PASS
```

------

# 三十一、为什么不强求 GitHub MCP Live Smoke

WP6 Final Gate 没有执行真实 GitHub MCP Live Smoke。

但核心问题：

```text
Session Lifecycle
Reconnect
stdio Wire
Schema Revalidation
Generation
Side-effect Safety
```

已经通过真实本地 Child Process 验证。

GitHub MCP 只会增加：

```text
网络
Credential
第三方状态
Rate Limit
```

不确定性。

所以当前把它作为：

```text
optional smoke
```

而不是 Hard Gate。

------

# 三十二、工程方法类问答

## Q1：MCP Server 断线后直接重新连接不行吗？

不行。

Reconnect 后还必须确认：

```text
Provider Identity
Tool Identity
Input Schema
```

没有变化。

否则 Transport 虽然恢复，Runtime Contract 可能已经变了。

------

## Q2：为什么 Session 要有 Generation？

为了隔离旧 Session 与新 Session。

旧 Invocation 不能因为 Reconnect 偷偷切到新的 Client。

------

## Q3：为什么 Schema 变化不能直接热更新？

因为 Tool Schema 属于 LocalAgent Typed Validation / Governance Contract。

Remote MCP Server 不应该运行时自行修改 Runtime Safety Contract。

------

## Q4：为什么 Extra Tool 可以忽略？

因为 Extra Tool 不属于 Startup 时冻结的 Registry。

只要原有 Frozen Tool Identity/Schema 都保持一致，新 Tool 不会影响现有 Contract。

------

## Q5：为什么 Missing Tool 却不能忽略？

因为 Registry 已经承诺这个 Tool 存在。

如果远端实际没有，Registry Truth 和 Provider Reality 就冲突了。

------

## Q6：为什么 Read-only Tool 可以 Replay？

因为 Local Frozen Policy 已证明：

```text
side_effect_kind = NONE
idempotency = READ_ONLY
```

在严格条件下重复执行不会改变外部状态。

------

## Q7：为什么 remote `readOnlyHint` 不可信？

因为 Remote Provider 是外部输入。

Governance Authority 必须在 LocalAgent，而不是让 MCP Server 自己决定风险等级。

------

## Q8：为什么 Side-effect Tool 不能 Replay？

因为连接断开不能证明第一次执行没发生。

必须进入 WP5 UNKNOWN。

------

## Q9：为什么 Reconnect 成功也不能 Replay Side-effect？

Reconnect 只恢复 Transport，不会告诉你旧 Operation 的真实结果。

------

## Q10：为什么 Reconnect 不是 Tool Retry？

Reconnect 解决：

```text
Session availability
```

Tool Retry 解决：

```text
某次 invocation 是否应该再次执行
```

是两层不同语义。

------

# 三十三、30 秒面试总结

我们 MCP 在 Stage5 已经接进统一 Tool Runtime 了，Stage7 主要补的是生产级 Session Lifecycle。

现在 MCP Server 断开以后不会直接盲重连使用，而是进入 DEGRADED，然后通过单一 Reconnect Owner 做有界指数退避。新的 Session 只有完成 initialize、Provider Identity、Frozen Tool Identity 和 Schema Digest 验证以后，才会以新的 Session Generation 原子发布。

另外我们把 Transport Retry 和 Tool Retry 分开。只读 Tool 在本地 frozen policy 确认安全以后最多可以跨 generation replay 一次；Side-effect Tool 断线后绝不自动 replay，而是进入前面 Tool Runtime 的 durable UNKNOWN，然后根据 Provider 能力做 Reconciliation。

------

# 三十四、2 分钟面试总结

我们 MCP 在更早阶段已经完成了 ToolRegistry、Governance 和 Adapter 接入，所以这次没有重建第二套 Tool Runtime，而是在现有 `McpIntegrationComponent` 上增加 resilient session lifecycle。

MCP Component 是 application-scoped 的唯一 Session 和 Reconnect Owner。一个 Session 从 STARTING 进入 AVAILABLE，遇到 EOF、Process Exit、Read/Write Failure 后进入 DEGRADED，再通过 bounded exponential backoff 和 jitter 进入 RECONNECTING。

Reconnect 不是“重新启动成功就继续用”。每个新的 Candidate Session 会先 initialize、执行 tools/list，然后重新验证 Provider Identity、Frozen Tool Identity 和 canonical Input Schema Digest。只有全部一致以后才发布为新的 Session Generation。旧 Handle 永远绑定旧 Generation，不会被偷偷换成新 Client。

我们还特别区分了 Read-only 和 Side-effect Tool。Read-only 是否允许 Replay 完全由 LocalAgent Frozen ToolExecutionSpec 决定，不信任 MCP Server 自己的 `readOnlyHint`。满足安全条件时最多 Replay 一次。

Side-effect Tool 则绝不因为 MCP Reconnect 自动重放。我们用真实 PostgreSQL + ToolExecutionService + stdio MCP subprocess 验证过，Tool 在 `PREPARED → STARTED` 后断线会进入 WP5 durable UNKNOWN，Provider Call Count 保持 1。即使 Session 随后恢复到 Generation 2，旧 Invocation 仍然保持 UNKNOWN。

所以 MCP Reconnect 解决的是 Transport Availability，不会越权改变 Tool Outcome、Registry 或 Governance Truth。

------

# 三十五、高频追问

## 1. MCP Session 挂了你们怎么处理？

```text
invalidate current session
→ DEGRADED
→ bounded reconnect
→ fully validate candidate
→ generation + 1
→ AVAILABLE
```

------

## 2. MCP Tool Schema 更新了怎么办？

当前不会动态升级。

```text
Schema Digest mismatch
→ Fail Closed
→ DEGRADED
```

需要 Operator / Restart / Reconfiguration。

------

## 3. Server 多了一个新 Tool 怎么办？

忽略。

不会自动进入 ToolRegistry。

------

## 4. Server 少了一个 Tool 怎么办？

Reconnect candidate 不可用。

因为 Frozen Registry 已经承诺那个 Tool 存在。

------

## 5. 为什么 Version 变化还允许 Reconnect？

因为 Phase9 Contract 中 version 只是 Metadata，不是严格 Provider Identity。

严格 compatibility 当前使用：

```text
configured server_id
+
serverInfo.name
```

------

## 6. Side-effect MCP Tool 断线后怎么办？

禁止 Replay。

进入 WP5：

```text
UNKNOWN
```

------

## 7. Provider 没有 status/query API 怎么办？

UNKNOWN 保持 UNKNOWN。

需要 Operator / Manual Resolution。

------

## 8. Read-only MCP Tool 能无限重试吗？

不能。

最多跨新的 validated generation Replay 一次。

------

## 9. Shutdown 时 MCP Server 会不会重新起来？

不会。

`CLOSED` 是终态，Reconnect scheduling 有 CLOSED Guard。

------

## 10. 为什么不用动态 Tool Hot Reload？

因为那会让外部 MCP Server 在 Runtime 运行期间修改 LocalAgent Registry / Governance Contract。

当前明确不支持。

------

# 三十六、Bad Case

## Bad Case 1：Reconnect Success 就直接 AVAILABLE

没有验证 Identity / Tool / Schema。

------

## Bad Case 2：Schema 改了自动 Registry.update()

让 Remote Provider 动态修改 Runtime Contract。

------

## Bad Case 3：MCP Server 说 readOnly=true 就允许 Replay

恶意 Server 可以给 destructive Tool 伪造 Hint。

------

## Bad Case 4：Side-effect disconnect → Reconnect → Replay

第一次可能已经成功，制造重复副作用。

------

## Bad Case 5：旧 Session Handle 自动切换到新 Client

Invocation 执行上下文变得不可追踪。

------

## Bad Case 6：每个 Transport Error 都起一个 Reconnect Task

可能 Spawn 多个 MCP Server。

------

## Bad Case 7：无限 Reconnect

Provider 永久故障时产生忙循环、日志风暴和进程风暴。

------

## Bad Case 8：Shutdown 只关闭 Current Client

之前 Broken 但仍 Owned 的 Child Process 可能泄漏。

------

## Bad Case 9：CLOSED 后 Late Callback 再次 Reconnect

Application Shutdown 后又偷偷 Spawn Child。

Final Gate 实际发现并修过。

------

# 三十七、本 WP 最重要的三个知识点

## 第一：Reconnect 是重新建立信任，不只是恢复连接

需要重新验证：

```text
Provider Identity
Tool Identity
Schema Digest
```

------

## 第二：Session Truth 和 Operation Truth 必须分开

```text
MCP AVAILABLE
```

只代表 Transport 可以用了。

不代表：

```text
旧 Side-effect Invocation 没执行
```

------

## 第三：Replay Authority 必须来自 Local Governance

Remote MCP Metadata 不能自己决定：

```text
Read-only
Side-effect
是否允许 Replay
```

------

# 三十八、WP5 与 WP6 可以怎么一起回答面试

可以这样说：

> MCP Server 断线时，我们先判断这是 Transport Failure 还是 External Operation Uncertainty。Read-only Tool 可以在新的、经过 Identity 和 Schema 验证的 Session Generation 上最多 Replay 一次；但 Side-effect Tool 不允许因为 Transport 恢复就自动重新调用。只要操作可能已经跨过外部副作用边界，就进入 durable UNKNOWN，由 Provider-specific Reconciliation 决定最终结果。

这个回答基本同时体现：

```text
MCP Lifecycle
Idempotency
Fencing
UNKNOWN
Reconciliation
Governance
```

------

# 三十九、Truth / Completion Boundary

## 已真实完成

### Application-scoped Lifecycle Owner

`McpIntegrationComponent` 是唯一 Session / Reconnect Owner。

### Lifecycle State Machine

```text
STARTING
AVAILABLE
DEGRADED
RECONNECTING
DISABLED
CLOSED
```

### Session Generation

Reconnect 成功递增 generation。

### Immutable Session Handle

旧 Handle 不自动切换新 Client。

### Atomic Candidate Publication

Candidate 完成全部验证后才发布。

### Bounded Reconnect

有界 Attempts。

### Exponential Backoff

支持指数退避。

### Jitter

支持 bounded jitter。

### Single Reconnect Owner

多个 Failure 不会 Spawn 多个并行 Reconnect。

### Provider Identity Revalidation

使用 Phase9 Frozen Identity Contract。

### Tool Identity Revalidation

Frozen Required Tool 缺失时 Fail Closed。

### Schema Digest Revalidation

Schema 改变时拒绝 Candidate。

### Extra Tool Ignored

不会动态注册。

### Frozen ToolRegistry

Reconnect 不修改 Registry。

### Frozen Governance

Remote annotations 不能覆盖本地 ToolExecutionSpec / Policy。

### Read-only Replay Max Once

严格本地 Policy + Generation 条件下最多 Replay 一次。

### Side-effect Replay Forbidden

断线不自动 Retry。

### WP5 UNKNOWN Integration

Side-effect MCP Tool Disconnect：

```text
PREPARED
→ STARTED
→ UNKNOWN
```

真实 PostgreSQL 已验证。

### Deadline

Replay / Wait for Generation 受 Caller Remaining Budget 限制。

### Cancellation

Cancel 不会产生自动 Replay。

### Clean Shutdown

Reconnect Task、Background Task、Owned Child 全部清理。

### Real stdio MCP Evidence

真实 Subprocess + JSON-RPC：

```text
initialize
notifications/initialized
tools/list
tools/call
```

已验证。

### Production Reachability

真实 Production Tool Runtime 使用 Lifecycle-managed MCP Session。

------

# 四十、尚未完成

## HTTP MCP

未实现。

## SSE / Streamable HTTP MCP

未实现。

## Dynamic Tool Hot Reload

未实现。

## Registry / Policy Hot Mutation

未实现。

## Multi-provider HA / Failover

未实现。

## GitHub MCP Live Smoke

未执行。

## Universal Side-effect Reconciliation

未实现。

如果 Provider 没有：

```text
status/query API
```

则：

```text
UNKNOWN
→ Operator / Manual
```

------

# 四十一、面试中不能夸大的地方

不要说：

> “MCP Server 更新 Tool Schema 后我们会自动升级。”

应该说：

> “当前 Schema 变化会 Fail Closed，不支持 Runtime Hot Reload。”

不要说：

> “MCP Tool 断线都可以自动 Retry。”

应该说：

> “只有 Local Governance 判断为严格 Read-only 的 Tool 才允许最多一次 Replay，Side-effect 一律不 Replay。”

不要说：

> “Reconnect 后之前未知的副作用就解决了。”

应该说：

> “Session Availability 和 Operation Outcome 是独立 Truth；Reconnect 不会自动改变旧 UNKNOWN。”

不要说：

> “我们已经支持所有 MCP Transport。”

应该说：

> “当前 Stage7 Scope 是 STDIO_ONLY。”

------

# 四十二、一句话总结

> WP6 的本质不是“给 MCP 加个重连”，而是把 **Session Lifecycle + Generation Isolation + Identity/Schema Revalidation + Singleflight Reconnect + Local Governance Replay Policy + WP5 UNKNOWN Safety** 串成一个不会因为 Transport 恢复而破坏 Runtime Safety Contract 的 MCP 生产闭环。