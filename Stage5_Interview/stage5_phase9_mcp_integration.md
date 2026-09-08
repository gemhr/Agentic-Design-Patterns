# Stage5-Phase9 — MCP Integration 完整学习 / 面试总结

推荐文件名：

```text
docs/interview/mcp_integration.md
```

------

# 1. Phase9 的目标是什么

Phase9 的核心目标不是：

```text
给 LocalAgent 再做一套 MCP Runtime
```

而是：

> **把 MCP Server 作为 External Tool Provider（外部工具提供方），接入 LocalAgent 已经冻结并验证过的 Tool Runtime。**

Phase9 开始前，LocalAgent 已经具备：

```text
ToolRegistry
ToolAdapter
Typed ToolInvocation
Validation
ToolGovernanceService
ToolApprovalController
Execution Claim / CAS
ToolExecutionService
DeepSeek Native Function Calling
role=tool continuation
HITL
Journal / Persistence
```

所以 MCP 的正确位置只能是：

```text
External MCP Server
        ↓
MCP Client
        ↓
MCP-backed ToolAdapter
        ↓
Existing Tool Runtime
```

而不能变成：

```text
External MCP Server
        ↓
Second MCP Runtime
        ↓
Second Governance
        ↓
Second Execution System
```

整个 Phase9 最核心的一句话：

> **MCP 是 Tool Provider Protocol，不是 LocalAgent 的第二套 Tool Runtime。**

------

# 2. Phase9 最终完成状态

Phase9 原始正式 Final Gate 已经：

```ini
PHASE9_FINAL_GATE = PASS
ARCHITECTURE_COMPLIANCE = PASS
ARCHITECTURE_REOPEN_REQUIRED = NO
BLOCKING_P1_COUNT = 0
READY_TO_CLOSE_PHASE9 = YES
```

当时已经真实证明：

```text
MCP Client / Discovery
MCP-backed ToolAdapter
Tool Runtime Integration
Governance Reuse
HITL Reuse
Side-effect Semantics
Real MCP Protocol E2E
Real Remote Model E2E
Real HITL E2E
```

但当时仍保留一个真实性边界：

```ini
REAL_MCP_PROTOCOL_E2E = PASS
CROSS_IMPLEMENTATION_MCP_INTEROP = NOT_PROVEN
```

原因是 WP3 使用的 MCP Server 虽然是：

```text
独立 subprocess
真实 stdio
真实 JSON-RPC
标准 MCP 2025-06-18
不 import LocalAgent
```

但仍然由本项目自行实现。

之后 WP4 作为 Phase9 的 Post-close Extension（收口后扩展验证），真实接入 GitHub 官方 MCP Server，最终补齐：

```ini
GITHUB_OFFICIAL_MCP_INTEROP = PASS
CROSS_IMPLEMENTATION_MCP_INTEROP = PASS

REAL_GITHUB_MCP_MUTATION_E2E = PASS
REAL_HITL_GITHUB_MCP_E2E = PASS

GITHUB_MUTATION_EXACTLY_ONCE = PASS
GITHUB_REJECT_ZERO_EXECUTION = PASS
```

最终 GitHub mutation 使用真实 `issue_write(method=create)`，APPROVE 后 GitHub 实际创建一个 Issue，duplicate APPROVE 后仍只有一次 MCP execution 和一个 Issue；REJECT 路径 MCP call 与 GitHub side effect 都为 0。

------

# 3. Phase9 的 WP 路线

最终 Phase9 可以理解为：

```text
Phase9 — MCP Integration

├─ WP0 — MCP Architecture Decision
│
├─ WP1 — MCP Client + Discovery Boundary
│
├─ WP2 — MCP-backed ToolAdapter
│        + Existing Runtime Integration
│
├─ WP3 — Real MCP Protocol E2E
│        + HITL Closeout
│
└─ WP4 — GitHub Official MCP Interoperability
         ├─ Read-only Cross-implementation E2E
         ├─ EmbeddedResource Compatibility
         └─ Mutation + HITL + Exactly-once
```

每一步的目标都不同：

```text
WP0：决定边界
WP1：能连接、能发现
WP2：能进入现有 Runtime
WP3：证明完整真实协议链
WP4：证明第三方官方实现真的兼容
```

------

# 4. WP0 — MCP Architecture Decision

## 4.1 为什么必须先做 Architecture Decision

MCP 接入表面看像：

```text
启动 subprocess
→ tools/list
→ tools/call
```

但真正复杂的是 Owner 问题：

```text
谁拥有 Client？
谁拥有 Session？
谁决定 Tool Identity？
谁决定 Risk？
谁决定 Approval？
谁决定 Timeout？
谁决定 Cancellation？
谁决定 Retry？
谁决定 Side-effect Truth？
```

如果这些问题不提前冻结，很容易出现：

```text
Tool Runtime
+
MCP Runtime
```

双 Owner。

所以 WP0 的核心工作不是写代码，而是冻结 Ownership Boundary。

------

# 5. WP0 最终冻结的核心 Architecture

最终决定：

```text
MCP Server
    ↓
MCP Client
    ↓
MCP Integration Component
    ↓
MCP-backed ToolAdapter
    ↓
Existing ToolRegistry
    ↓
Existing Governance
    ↓
Existing ToolExecutionService
```

MCP 不能绕过：

```text
Typed Validation
ToolPolicy
Governance
Approval
Claim / CAS
Execution
Retry Authority
Side-effect Truth
```

------

# 6. MCP Integration Seam（集成接缝）

最终最佳接入点是：

```text
MCP Tool
    ↓
McpBackedToolAdapter
    ↓
ToolRegistration
    ↓
Existing ToolRegistry
```

这实际上是一个典型：

> **Anti-Corruption Layer（防腐层）**

MCP 世界可能有：

```text
MCP Tool Schema
MCP Tool Name
MCP annotations
MCP CallToolResult
```

LocalAgent Runtime 世界则有：

```text
ToolInvocation
ToolExecutionSpec
ToolPolicy
ToolAdapterResponse
ToolOutput
```

Adapter 的作用就是：

```text
External Protocol Model
        ↓
转换
        ↓
Internal Runtime Model
```

而不是让 Runtime Core 直接理解 MCP。

------

# 7. 为什么 MCP Tool 不能直接执行

错误路线：

```text
Model
→ MCP Client
→ tools/call
```

这样会跳过：

```text
Typed Validation
Risk Evaluation
HITL
Claim / CAS
Retry
Side-effect Tracking
```

正确路线：

```text
Model
→ ToolInvocation
→ Governance
→ Approval
→ Claim
→ ToolExecutionService
→ MCP Adapter
→ MCP Server
```

所以：

> **MCP Tool 与 Built-in Tool 在 Provider 层不同，但进入 Runtime 后必须服从同一条 Execution Authority。**

------

# 8. Identity（身份）设计

MCP 接入必须区分至少三个概念：

```text
server_id
remote_name
local canonical tool_name
```

例如 GitHub：

```text
server_id    = github_official
remote_name  = issue_write
local_name   = github_issue_write
```

不能直接拿：

```text
issue_write
```

当 Runtime 全局身份。

因为另外一个 MCP Server 也可能有：

```text
issue_write
```

或：

```text
read_file
```

------

# 9. Remote Identity ≠ Local Canonical Identity

Runtime 真正依赖的是：

```text
local canonical tool_name
```

它会进入：

```text
Policy
Governance
ToolInvocation
Journal
Evaluation
Model-visible definition
```

而：

```text
server_id
remote_name
```

主要是：

```text
Provider provenance
```

所以：

> **远端 Provider Identity 和本地 Runtime Identity 必须分开。**

------

# 10. MCP Tool Identity 也不等于 operation_id

还必须区分：

```text
Tool Identity
Operation Identity
Idempotency Identity
Approval Identity
```

例如：

```text
github_issue_write
```

只是工具身份。

具体一次创建 Issue：

```text
operation_id
```

是一次业务操作身份。

而：

```text
approval_id
```

又是一次审批身份。

不能混为一谈。

------

# 11. MCP Metadata 为什么是不可信的

MCP Tool 可能声明：

```text
readOnlyHint
destructiveHint
idempotentHint
openWorldHint
```

这些信息可以用于：

```text
description
operator reference
UI
diagnostic
```

但不能直接作为：

```text
Risk
Authorization
Idempotency
Approval
Retry
```

的 Authority。

因为这些 Metadata 来自：

```text
External Provider
```

属于：

> **Provider Claim（提供方声明）**

而不是：

> **Runtime Fact（运行时事实）**

------

# 12. Local Governance 必须是最终 Authority

例如 Provider 声明：

```text
readOnlyHint=true
```

但 Local Mapping 明确：

```text
side_effect_kind = LOCAL_STATE_MUTATION
idempotency = NON_IDEMPOTENT
```

则 Runtime 必须：

```text
HIGH
→ APPROVAL_REQUIRED
```

不能让：

```text
readOnlyHint
```

把风险降低。

一句话：

> **MCP metadata can inform, but cannot authorize.**

------

# 13. Registration 和 Policy 为什么要原子覆盖

一个危险状态：

```text
ToolRegistry
有 Tool

但

ToolPolicyCatalog
没有 Policy
```

这意味着：

```text
Model 能选择 Tool
但 Runtime 不知道如何治理
```

属于：

> **Security Coverage Hole（安全覆盖漏洞）**

所以 MCP 注册原则：

```text
Discovery
→ Local Mapping
→ Risk Classification
→ ToolRegistration
→ ToolPolicy
→ Registry Freeze
```

任一步失败：

```text
整个该 Server registration fail closed
```

------

# 14. Discovery 为什么选择 Startup Snapshot

Phase9 没有实现：

```text
listChanged
dynamic refresh
hot reload
```

而是：

```text
Application Startup
    ↓
initialize
    ↓
tools/list
    ↓
immutable discovery snapshot
    ↓
registration
    ↓
freeze
```

原因：

```text
Determinism
Security
Owner 简单
Policy 一致
Identity 稳定
```

代价是：

```text
运行时 MCP Tool 变化不会自动刷新
```

这是明确 Accepted Limitation，而不是遗漏。

------

# 15. MCP Lifecycle（生命周期）

MCP Client Owner：

```text
Application Scope
```

由：

```text
server.py::lifespan
```

创建 MCP Integration Component。

Session：

```text
Per configured MCP server
```

并在 Application Lifecycle 中：

```text
startup
→ initialize
→ discovery
→ reuse
→ shutdown
```

而不是：

```text
每次 Tool Call
→ 启一个进程
→ initialize
→ call
→ close
```

这样可以避免：

```text
重复 handshake
进程泄漏
session drift
```

------

# 16. Transport 为什么选择 stdio

WP0 最终选择：

```text
STDIO_FIRST
```

而不是一开始做：

```text
Streamable HTTP
```

理由不是：

```text
stdio 永远更好
```

而是当前项目环境：

```text
单机
内网
本地 Process Lifecycle
面试展示
Integration Test
```

stdio 可以最小成本完成：

```text
real server
real protocol
real lifecycle
real tools/call
```

而无需额外：

```text
HTTP server lifecycle
network auth
reverse proxy
connection policy
remote deployment
```

------

# 17. Streamable HTTP 为什么没有做

因为当前 Phase9 的目标是：

```text
MCP Integration correctness
```

而不是：

```text
Transport Portfolio
```

所以：

```text
Streamable HTTP
```

被明确 defer。

如果未来：

```text
MCP Server 跨机器
Provider 平台化
集中 MCP Market
```

才值得增加。

------

# 18. WP1 — MCP Client + Discovery Boundary

WP1 实现：

```text
StdioMcpClient
```

负责：

```text
subprocess lifecycle
JSON-RPC
initialize
initialized notification
tools/list pagination
bounded close
```

支持协议：

```text
MCP 2025-06-18
```

同时建立：

```text
McpDiscoverySnapshot
```

作为启动时不可变 Discovery 结果。

------

# 19. WP1 Client 不负责什么

MCP Client 不负责：

```text
Tool Governance
Risk
Approval
Retry Policy
Side-effect Truth
Runtime Cancellation Authority
```

Client 只负责：

```text
Protocol transport
Session
Request / Response
```

这是一个很关键的 Owner Boundary。

------

# 20. WP1 Bad Case — subprocess shutdown 无界等待

真实 Codex Review 发现：

```text
kill()
之后 process.wait()
没有真正 bounded
```

风险：

```text
MCP child 不退出
→ application shutdown hang
```

修复：

```text
bounded multi-stage shutdown budget
```

知识点：

> **调用 kill 不代表 Lifecycle 已经有 Bound。**

------

# 21. WP1 Bad Case — 只限制 JSON Size 不够

最初只控制：

```text
response size
```

但恶意或异常 Provider 可以发送：

```text
非常深的 JSON
```

即使总字节不大，也可能造成：

```text
recursion
parser cost
structure abuse
```

因此增加：

```text
MAX_JSON_STRUCTURE_DEPTH
```

以及：

```text
finite JSON validation
```

用于相关 Discovery / metadata 边界。

知识点：

> **Resource Bound 不只是 Byte Bound，还包括 Structural Complexity。**

------

# 22. WP2 — MCP-backed ToolAdapter

WP2 开始把 Discovery 出来的 MCP Tool 真正变成 Runtime Tool。

主链：

```text
McpDiscoverySnapshot
→ operator mapping
→ McpBackedToolAdapter
→ ToolRegistration
→ ToolPolicy
→ ToolRegistry
```

Model 后面看到的：

```text
github_get_file_contents
```

和 Built-in Tool 在 Runtime 看来是同一种：

```text
registered Tool
```

------

# 23. MCP-backed ToolAdapter 的职责

Adapter 主要负责：

```text
MCP schema
→ Local typed invocation

Local Tool execution
→ MCP tools/call

MCP result
→ ToolAdapterResponse
```

但不负责：

```text
Risk
Approval
Retry Authority
Claim
```

这就是防腐层的意义。

------

# 24. Validation 必须在 Governance 前

链路保持：

```text
Model arguments
→ Typed Validation
→ immutable ToolInvocation
→ Governance
```

而不是：

```text
Model arguments
→ Governance
→ Validation
```

因为 Governance 判断：

```text
risk
side effect
permission
```

应该针对：

```text
已经确定、合法、不可变的 invocation
```

而不是一坨未经验证的动态 JSON。

------

# 25. Mutation Side-effect Checkpoint

对于：

```text
mutation MCP Tool
```

必须在 outbound call 前：

```text
before_side_effect()
```

标记：

> 从这里开始 Runtime 已经不能再安全声称“绝对没有副作用”。

然后：

```text
MCP tools/call
```

------

# 26. Mutation 的 Side-effect Truth

最终语义：

```text
成功执行
→ COMMITTED

超时 after outbound
→ UNKNOWN

Cancellation after checkpoint
→ UNKNOWN

Provider isError after outbound mutation
→ UNKNOWN

Protocol success
但 Result 类型不支持
→ COMMITTED + Result Failure
```

最重要的一句话：

> **Execution Fact 和 Result Decoding 是两回事。**

------

# 27. Read-only 和 Mutation 的错误语义不同

Read-only：

```text
isError
→ NOT_STARTED / failure
```

因为没有预期副作用。

Mutation：

```text
isError after provider_started
→ UNKNOWN
```

因为 Provider 返回：

```text
error
```

并不能证明：

```text
没有执行任何副作用
```

------

# 28. Retry Authority 为什么不能交给 MCP Client

一个错误实现：

```text
MCP tools/call timeout
→ MCP Client 自动 reconnect
→ replay request
```

如果 Tool 是：

```text
create_issue
transfer_money
delete_resource
```

可能导致重复副作用。

因此：

```text
MCP Client
→ NO automatic retry
→ NO reconnect-and-replay
```

真正的：

```text
Retry Authority
```

仍属于：

```text
ToolExecutionService / Runtime
```

------

# 29. Timeout 为什么会让 Session Broken

Phase9 当前设计中：

```text
MCP request timeout
→ break session
```

后续调用：

```text
MCP_SESSION_UNAVAILABLE
```

而不是：

```text
自动 reconnect
→ 自动 replay
```

这虽然影响 Availability（可用性），但提高了：

```text
Side-effect Safety
```

属于明确 Accepted Limitation。

------

# 30. WP3 — Real MCP Protocol E2E

WP3 创建：

```text
demo/mcp_demo_server.py
```

但这个 Demo Server：

```text
独立 subprocess
不 import LocalAgent
标准 JSON-RPC
标准 MCP 2025-06-18
```

提供：

```text
get_demo_status
append_demo_record
```

分别对应：

```text
read-only
mutation
```

------

# 31. 为什么 Demo MCP Server 仍然有价值

它不是生产 MCP Provider。

它长期适合作为：

```text
Deterministic E2E Fixture
Protocol Regression
Offline Demo
HITL regression
Exactly-once proof fixture
```

不应该“扶正”为 LocalAgent Production MCP Server。

------

# 32. WP3 Read-only E2E

真实链：

```text
Natural Language
→ Real DeepSeek
→ MCP-backed read Tool
→ Governance ALLOW
→ MCP tools/call
→ Tool Result
→ role=tool
→ Final Answer
```

这证明：

```text
Model
Runtime
MCP Server
Tool Continuation
```

整个链路可以真实工作。

------

# 33. WP3 Mutation APPROVE E2E

真实：

```text
Natural Language
→ mutation Tool
→ HIGH
→ APPROVAL_REQUIRED
→ HTTP APPROVE
→ Claim
→ MCP tools/call
→ side effect
```

并且：

```text
duplicate APPROVE
→ idempotent
→ only one execution
```

------

# 34. WP3 REJECT E2E

真实：

```text
Natural Language
→ mutation Tool
→ APPROVAL_REQUIRED
→ HTTP REJECT
```

结果：

```text
TOOL_STARTED = 0
MCP call = 0
external state delta = 0
```

所以证明：

```text
zero execution
```

------

# 35. Exactly-once 来自哪里

必须记住：

> **Exactly-once 不是 MCP 提供的。**

真正来源：

```text
Approval Binding
+
Execution Claim
+
CAS
```

MCP 只在：

```text
Claim 成功以后
```

作为 External Executor 被调用。

------

# 36. WP3 真实 Bad Case — DeepSeek tool-call content=None

真实 Provider Wire 中，Assistant Tool Call Message 可以：

```python
content = None
```

但 LocalAgent Token Estimator 最初假设：

```python
content is str
```

导致：

```text
Tool 实际成功
→ continuation 前
→ TypeError
```

修复：

```python
message.get("content") or ""
```

这个 Bad Case 很适合面试讲。

知识点：

> **Provider Protocol 的合法 Nullability 必须一直传播到内部辅助组件，不能只在主解析链正确。**

------

# 37. Original Phase9 Final Gate 的 Truth Boundary

当时 Final Gate 已经可以说：

```text
REAL_MCP_PROTOCOL_E2E = PASS
```

但不能说：

```text
CROSS_IMPLEMENTATION_MCP_INTEROP = PASS
```

因为 Demo Server 仍是项目自行实现。

这一点后来通过 WP4 补齐。

这个历史过程不要删除。

面试时反而可以讲：

> 我没有因为自建 Client 和自建 Server 跑通就直接声称支持第三方 MCP，而是单独增加 GitHub 官方 MCP Server 做 cross-implementation validation。

这体现了：

```text
Truthful Engineering
```

------

# 38. WP4 — GitHub Official MCP Interoperability

WP4 接入：

```text
github/github-mcp-server
```

运行方式：

```text
official Docker image
+
stdio
```

先只开放：

```text
get_file_contents
```

验证：

```text
initialize
tools/list
registration
DeepSeek selection
Governance
tools/call
continuation
```

------

# 39. GitHub Cross-implementation 的真实意义

这次双方实现方不同：

```text
Client：
LocalAgent

Server：
GitHub Official MCP Server
```

所以终于可以证明：

```ini
CROSS_IMPLEMENTATION_MCP_INTEROP = PASS
```

但这个 PASS 只表示：

> 至少验证了一个外部官方 MCP implementation。

不能扩大成：

```text
所有 MCP Server 都兼容
```

------

# 40. WP4 第一处真实 Compatibility Gap：EmbeddedResource

第一次真实：

```text
get_file_contents
```

失败：

```text
MCP_TOOL_RESULT_UNSUPPORTED
```

调查后发现 GitHub 返回：

```text
TextContent
+
EmbeddedResource(TextResourceContents)
```

真正 README 正文位于：

```text
resource.text
```

而 LocalAgent 原来只接受：

```text
TextContent
```

所以问题不是：

```text
GitHub 特殊格式
```

而是：

```text
LocalAgent MCP CallToolResult supported subset 过窄
```

------

# 41. 为什么这里需要 Narrow Architecture Reopen

原 WP0 已冻结：

```text
TEXT_CONTENT_AND_ISERROR_ONLY
```

所以不能直接偷偷修改。

进行了一个：

```ini
REOPEN_SCOPE =
MCP_CALL_TOOL_RESULT_NORMALIZATION_ONLY
```

最终批准：

```text
TextContent
EmbeddedResource(TextResourceContents)
isError
```

继续拒绝：

```text
BlobResourceContents
ResourceLink
Image
Audio
structured-only
task
```

并保持：

```ini
TOOLS_ONLY_FOR_PHASE9 = YES
MCP_RESOURCES_PRIMITIVE_REQUIRED = NO
```

------

# 42. EmbeddedResource 不等于 MCP Resources

这是 Phase9 必背知识点。

## Embedded Resource

```text
tools/call
→ content[]
→ EmbeddedResource
→ resource.text
```

数据已经返回。

## Resources Primitive

```text
resources/list
resources/read
resources/subscribe
```

需要新的请求和生命周期。

所以：

```text
支持 EmbeddedResource
```

不能说：

```text
实现了 MCP Resources
```

------

# 43. Embedded Text 最终怎么实现

最终 production 只修改：

```text
mcp/models.py
```

没有修改：

```text
ToolOutput
ToolInvocation
ToolExecutionService
Governance
Journal
Snapshot
Recovery
```

`mcp/adapter.py` 已经有：

```text
ordered newline join
```

逻辑，所以不需要再改。

------

# 44. Embedded Resource URI 为什么不 Fetch

当前规则：

```text
resource.uri
→ structural validation
→ discard
```

明确：

```text
NO fetch
NO resolve
NO resources/read
NO filesystem access
```

因为正文：

```text
resource.text
```

已经 embedded。

否则一个 Result Parser 会偷偷变成：

```text
Second External I/O Executor
```

这会重新引入：

```text
timeout
retry
auth
security
lifecycle
```

Owner 冲突。

------

# 45. Output Size Authority

没有新增：

```text
MCP_RESOURCE_MAX_BYTES
```

而继续：

```text
MCP wire framing
        ↓
Result normalization
        ↓
ToolExecutionSpec.max_output_bytes
        ↓
ToolOutput
```

最终唯一 Output Quota Authority：

```text
ToolExecutionSpec.max_output_bytes
```

因此现有：

```text
digest
original_size_bytes
returned_size_bytes
truncated
```

仍然可信。

------

# 46. GitHub Read-only 最终真实 PASS

真实：

```text
Natural Language
→ Real DeepSeek
→ github_get_file_contents
→ Governance ALLOW
→ GitHub Official MCP
→ EmbeddedResource
→ ToolOutput
→ role=tool
→ Final Answer
```

而且 Final Answer 使用了 README 正文中的真实内容，不是只看：

```text
download succeeded
```

生成答案。

------

# 47. 为什么 WP4 还继续做 Mutation

Read-only 证明：

```text
第三方 MCP Tool 可以工作
```

但 Agent Runtime 更重要的问题是：

```text
第三方 MCP Side Effect
是否仍然服从本地 Safety Runtime？
```

所以继续使用：

```text
GitHub official issue_write(method=create)
```

验证：

```text
Governance
HITL
Claim / CAS
Exactly-once
Reject zero-execution
```

------

# 48. GitHub Mutation Tool 的 Mapping

GitHub remote：

```text
issue_write
```

Local canonical name：

```text
github_issue_write
```

Local policy：

```text
side_effect_kind = LOCAL_STATE_MUTATION
idempotency = NON_IDEMPOTENT
```

得到：

```text
HIGH
→ APPROVAL_REQUIRED
```

真实 Discovery、Registration、Policy Coverage、Governance 均通过。

------

# 49. GitHub Writable ≠ Runtime Authorized

GitHub MCP 本轮不能开启：

```text
GITHUB_READ_ONLY=1
```

因为写 Tool 会被隐藏。

但：

```text
GitHub Server writable
```

只代表：

```text
Provider 有执行能力
```

仍不等于：

```text
Runtime 允许执行
```

真正权限链：

```text
Remote Capability
        ↓
Local Mapping
        ↓
Local ToolPolicy
        ↓
Governance
        ↓
APPROVAL_REQUIRED
```

------

# 50. Mutation APPROVE 最终真实 E2E

成功 Run：

```text
Natural Language
→ Real DeepSeek
→ github_issue_write
→ HIGH
→ APPROVAL_REQUIRED
→ HTTP APPROVE
→ Execution Claim
→ ToolExecutionService
→ GitHub Official MCP
→ issue_write(method=create)
→ GitHub Issue #1
```

用户自然语言没有明确告诉模型：

```text
issue_write
method=create
JSON
```

由 Real DeepSeek 自己完成 Tool Selection。

最终 GitHub 确实产生一个真实 Issue。

------

# 51. Duplicate APPROVE 与 Exactly-once

第一次：

```text
APPROVE
→ idempotent=false
```

同一个：

```text
run_id + approval_id
```

再 APPROVE：

```text
idempotent=true
```

最终内部：

```text
MCP call count = 1
```

外部：

```text
GitHub exact marker Issue count = 1
```

所以：

```ini
GITHUB_MUTATION_EXACTLY_ONCE = PASS
```

------

# 52. Exactly-once 的真正 Owner

必须明确：

```text
MCP ❌
GitHub ❌
Provider SDK ❌
```

真正 Owner：

```text
Approval
+
Claim
+
CAS
+
ToolExecutionService
```

所以换成另一个 MCP Server：

只要继续走：

```text
Existing Runtime
```

也可以复用相同 Exactly-once Safety。

------

# 53. REJECT Zero-execution

独立 REJECT Run：

```text
Natural Language
→ github_issue_write
→ APPROVAL_REQUIRED
→ HTTP REJECT
```

最终：

```text
TOOL_STARTED = 0
TOOL_COMPLETED = 0
MCP call = 0
GitHub marker Issue count = 0
```

所以：

```ini
GITHUB_REJECT_ZERO_EXECUTION = PASS
```

------

# 54. 为什么还要用 GitHub External State 做证据

Runtime 内部：

```text
TOOL_STARTED=0
```

已经很强。

但为了证明真实：

```text
external zero side effect
```

又查询：

```text
GitHub marker count
```

所以形成：

```text
Internal Runtime Evidence
+
External Provider State Evidence
```

双证据面。

------

# 55. WP4 Bad Case — localhost 被 Proxy 劫持

真实 E2E Harness 第一次：

```text
/api/chat
```

返回：

```text
HTTP 502
```

但请求根本没到 LocalAgent。

根因：

```text
Temporary HTTP Client
→ inherited proxy environment
```

修复：

```text
trust_env=false
```

这是：

```text
Harness-only fix
```

没有修改 production code。

知识点：

> **E2E Failure 必须先做 Failure Attribution，不能所有错误都归 Runtime。**

------

# 56. WP4 Bad Case — Mutation Target Owner 拼错

一度配置：

```text
gemhrrr
```

真实 Owner：

```text
gemhr
```

只读验证：

```text
configured repo → 404
provided link → PASS
```

系统没有：

```text
自动猜 owner
```

而是：

```text
BLOCKED_BY_ENVIRONMENT
```

这是正确行为。

知识点：

> **Mutation Target Identity 不能由 Agent 猜。**

------

# 57. WP4 Bad Case — PAT Credential Scope 403

真实 mutation 一度：

```text
GitHub issue_write
→ HTTP 403
```

诊断捕获实际 argument facts：

```text
method=create
owner=gemhr
repo=localagent-mcp-test
title_present=true
body_present=true
```

因此排除：

```text
MODEL_ARGUMENT_CONSTRUCTION
MCP_SCHEMA_COMPATIBILITY
```

最终：

```text
AUTH_CONFIGURATION_FAILURE
```

知识点：

> **Principal 有权限 ≠ Credential 有权限。**

账号本身可能：

```text
admin=true
```

但 Fine-grained PAT 如果没有：

```text
Issues: Read and write
```

真实 API 仍然会：

```text
403
```

------

# 58. Provider Error 为什么不能直接 Retry Mutation

当：

```text
issue_write
→ isError
```

Runtime 已经进入：

```text
provider_started=true
```

Side-effect Truth：

```text
UNKNOWN
```

不能：

```text
没看到 Issue
→ 自动 retry
```

否则可能出现：

```text
第一次其实成功
第二次又成功
→ duplicate Issue
```

所以：

```text
UNKNOWN
→ no automatic replay
```

------

# 59. 用户重新授权新 Run ≠ Automatic Retry

后来成功测试使用：

```text
全新 Run
+
全新 marker
+
用户明确授权
```

而不是重放旧 UNKNOWN invocation。

这个区别很重要：

```text
automatic retry
```

和：

```text
new user-authorized operation
```

完全不同。

------

# 60. GitHub Read-side Visibility Delay

最终成功后发生：

```text
LocalAgent completion = success
↓
立即 REST query
→ count 0
↓
稍后 query
→ count 1
```

GitHub 最终存在：

```text
Issue #1
```

这体现：

> **Execution Truth 和 External Read Observation 也不是一回事。**

一次：

```text
GET count=0
```

不能直接证明：

```text
mutation 没发生
```

------

# 61. Phase9 最重要的 Side-effect State Machine

面试建议记：

```text
NOT_STARTED
    │
    │ before_side_effect()
    ▼
POSSIBLY_STARTED
    │
    ├─ confirmed success
    │      ↓
    │   COMMITTED
    │
    └─ timeout / cancel / ambiguous provider result
           ↓
        UNKNOWN
```

核心不是变量名，而是：

> **不能把“不知道”伪装成“没发生”。**

------

# 62. MCP Tool Result 的当前支持子集

最终 Phase9 / WP4：

```text
SUPPORTED

TextContent

EmbeddedResource
└─ TextResourceContents

isError
```

仍不支持：

```text
BlobResourceContents
ResourceLink
ImageContent
AudioContent
structured-only
task-augmented result
```

------

# 63. 当前仍然是 Tools-only

即使支持：

```text
EmbeddedResource
```

仍然：

```ini
TOOLS_ONLY_FOR_PHASE9 = YES
```

未实现：

```text
resources/list
resources/read
resources/subscribe
Prompts
```

不要在面试中说：

```text
“我完整支持 MCP Resources”
```

------

# 64. Security Boundary（安全边界）

MCP Server 永远属于：

```text
Untrusted External Provider
```

即使它是：

```text
GitHub Official
```

也不能改变：

```text
Provider Result
→ UNTRUSTED_EXTERNAL_TOOL_OUTPUT
```

GitHub README 里如果包含：

```text
ignore previous instructions
```

也不能自动提升为：

```text
system authority
```

它只能作为：

```text
tool result content
```

进入后续模型上下文。

------

# 65. Secret Boundary

MCP subprocess 不允许：

```python
env = os.environ
```

完整继承 Parent Environment。

因为 Parent 里可能还有：

```text
DeepSeek API Key
DB credential
internal secret
```

所以：

```text
allowlist
+
operator-configured environment
```

只向 GitHub MCP 注入需要的 PAT。

------

# 66. Configuration Security

Operator Config 可以决定：

```text
command
arguments
server id
tool mapping
local policy facts
```

但 Secret-bearing 临时配置：

```text
repo 外
temporary
not logged
not committed
cleanup after E2E
```

WP4 最终：

```ini
GITHUB_SECRET_LEAK = NO
```

------

# 67. Phase9 关键 Bad Case 总表

## Bad Case 1 — subprocess kill 后仍无界 wait

真实性：

```text
CODEX_REVIEW_DISCOVERY
```

知识点：

```text
Lifecycle Bound
```

------

## Bad Case 2 — JSON 只有 Byte Limit，没有 Structure Limit

真实性：

```text
CODEX_REVIEW_DISCOVERY
```

知识点：

```text
Resource Complexity Bound
```

------

## Bad Case 3 — MCP annotations 覆盖 Local Risk

真实性：

```text
HYPOTHETICAL_BAD_CASE + DETERMINISTIC_TEST
```

知识点：

```text
Provider Claim ≠ Security Authority
```

------

## Bad Case 4 — MCP Client 自己 Retry Mutation

真实性：

```text
HYPOTHETICAL_BAD_CASE
```

知识点：

```text
Single Retry Authority
```

------

## Bad Case 5 — Tool 已注册但 Policy 缺失

真实性：

```text
HYPOTHETICAL_BAD_CASE + coverage design
```

知识点：

```text
Security Coverage Atomicity
```

------

## Bad Case 6 — mutation 成功但 unsupported result

真实性：

```text
DETERMINISTIC_TEST
```

知识点：

```text
Side-effect Truth ≠ Result Decode
```

------

## Bad Case 7 — DeepSeek Assistant Tool Call content=None

真实性：

```text
REAL_REMOTE_MODEL_E2E
IMPLEMENTATION_DISCOVERY
```

知识点：

```text
Provider Nullability
```

------

## Bad Case 8 — 自建 MCP Server 无法证明跨实现兼容

真实性：

```text
SOURCE_AUDIT / TRUTH BOUNDARY
```

知识点：

```text
Protocol E2E ≠ Interoperability
```

------

## Bad Case 9 — GitHub EmbeddedResource 不支持

真实性：

```text
REAL_GITHUB_MCP_E2E
IMPLEMENTATION_DISCOVERY
```

知识点：

```text
Supported Protocol Subset
```

------

## Bad Case 10 — GitHub-specific result parser

真实性：

```text
HYPOTHETICAL_BAD_CASE
```

知识点：

```text
Protocol Adapter vs Provider Hack
```

------

## Bad Case 11 — Embedded URI 自动 fetch

真实性：

```text
HYPOTHETICAL_BAD_CASE
```

知识点：

```text
Hidden External I/O
```

------

## Bad Case 12 — localhost 请求走系统 Proxy

真实性：

```text
REAL E2E HARNESS DISCOVERY
```

知识点：

```text
Failure Attribution
```

------

## Bad Case 13 — GitHub Owner 拼错

真实性：

```text
USER / ENVIRONMENT CONFIG DISCOVERY
```

知识点：

```text
Mutation Target Identity
```

------

## Bad Case 14 — PAT 缺 Issues Write

真实性：

```text
REAL_GITHUB_MCP_MUTATION_E2E
```

知识点：

```text
Principal Permission ≠ Credential Scope
```

------

## Bad Case 15 — Provider Error 后直接重试

真实性：

```text
REAL RISK AVOIDED
```

知识点：

```text
UNKNOWN must not auto replay
```

------

## Bad Case 16 — immediate GitHub count=0 推断 mutation 未执行

真实性：

```text
REAL_GITHUB_EXTERNAL_OBSERVATION
```

知识点：

```text
Execution Truth ≠ Read-side Visibility
```

------

# 68. 名词 / 概念速览

### MCP — Model Context Protocol（模型上下文协议）

用于 Host 与外部 Server 之间发现并调用 Tool、Resource、Prompt 等能力的开放协议。

### MCP Host（MCP 宿主）

拥有 MCP Client 并消费 MCP Server 能力的应用，LocalAgent 属于 Host。

### MCP Client（MCP 客户端）

负责与某个 MCP Server 建立 Session 并发送协议请求。

### MCP Server（MCP 服务端）

通过 MCP 暴露 Tool / Resource / Prompt 等能力的 Provider。

### External Tool Provider（外部工具提供方）

提供 Tool 实际能力但不拥有 Local Runtime Safety Authority 的外部系统。

### ToolAdapter（工具适配器）

把外部 Provider 协议模型转换为 Runtime 内部 Tool Contract 的防腐层。

### Anti-Corruption Layer（防腐层）

隔离外部协议模型与内部 Domain Model，避免外部概念污染 Runtime Core。

### Discovery（工具发现）

通过 `tools/list` 获取 Server 当前暴露的 Tool 描述。

### Startup Snapshot（启动快照）

启动阶段一次性发现并冻结 Tool Set。

### Canonical Tool Identity（规范工具身份）

Local Runtime 中稳定、唯一、可治理的 Tool Name。

### Provider Provenance（提供方来源）

记录 Tool 来自哪个 Server 和 Remote Name，但不作为 Runtime Identity。

### Provider Metadata（提供方元数据）

Server 自己声明的 annotations 等信息，只作为外部 Claim。

### Governance Authority（治理权威）

最终决定 ALLOW / DENY / APPROVAL_REQUIRED 的本地 Authority。

### HITL — Human-in-the-loop（人在回路）

高风险操作必须人工批准或拒绝。

### Claim（执行认领）

Runtime 为一次 Invocation 获取唯一执行权。

### CAS — Compare-And-Set（比较并设置）

原子判断旧状态并更新到新状态，用于并发安全。

### Exactly-once（恰好一次）

同一个逻辑操作最终只发生一次真实 Execution。

### Zero-execution（零执行）

审批拒绝后 Provider Execution 完全没有发生。

### Idempotency（幂等性）

同一操作重复执行是否与执行一次效果等价。

### Side-effect Truth（副作用事实）

Runtime 对外部副作用真实状态的判断。

### UNKNOWN（副作用未知）

无法确定 Provider 是否已经发生副作用。

### Retry Authority（重试权威）

系统中唯一可以决定是否重新执行操作的 Owner。

### Fail Closed（失败关闭）

无法证明安全时拒绝继续，而不是默认放行。

### EmbeddedResource（内嵌资源）

直接包含于 MCP Tool Result Content 中的 Resource。

### TextResourceContents（文本资源内容）

EmbeddedResource 内部携带 `text` 的文本资源结构。

### Resources Primitive（资源原语）

MCP 中 `resources/list/read/subscribe` 等独立资源能力。

### Tool Result Normalization（工具结果归一化）

把 MCP ContentBlock 转换为 LocalAgent 统一 ToolAdapterResponse 的过程。

### Cross-implementation Interoperability（跨实现互操作）

不同实现方开发的 Client 与 Server 可以按标准正确通信。

### Credential Scope（凭证权限范围）

Token 自己实际被授予的权限，而不是账号理论上拥有的权限。

------

# 69. 工程方法类问答

## Q1：为什么 MCP 不应该成为第二个 Tool Runtime？

因为 LocalAgent 已经有：

```text
Validation
Governance
HITL
Retry
Side-effect Truth
Claim / CAS
```

如果 MCP 自己再做这些，会出现：

```text
Double Owner
```

最终安全语义不一致。

------

## Q2：MCP Integration 最适合在哪一层做？

在：

```text
ToolAdapter Boundary
```

因为 External Protocol 和 Runtime Domain 正好在这里转换。

------

## Q3：为什么不让 Model 直接调用 MCP Client？

因为会绕过：

```text
Typed Validation
Governance
Approval
Execution Claim
```

------

## Q4：为什么远端 Tool Name 不直接当本地 Tool Name？

因为多个 Server 可能发生：

```text
name collision
```

而本地 Policy 需要稳定 Identity。

------

## Q5：为什么不信 MCP readOnlyHint？

因为它来自 Provider。

安全 Authority 必须：

```text
Local Policy
```

------

## Q6：为什么 Registration 和 Policy 要一起完成？

避免：

```text
Model-visible Tool
+
No Governance Coverage
```

------

## Q7：为什么使用 Startup Snapshot？

用：

```text
运行时动态能力
```

换取：

```text
Determinism
Security
Simple Lifecycle
```

------

## Q8：为什么 stdio first？

因为当前目标是：

```text
最小真实协议闭环
```

而不是：

```text
Remote Transport Platform
```

------

## Q9：为什么 Timeout 后不自动 reconnect？

因为对于 Mutation：

```text
timeout
```

无法证明：

```text
Provider 没执行
```

------

## Q10：为什么支持 EmbeddedResource 但不做 Resources？

因为数据已经随：

```text
tools/call
```

直接返回。

不需要：

```text
resources/read
```

------

## Q11：为什么 Adapter 不提前 truncate Embedded Text？

因为会让：

```text
original_size
digest
truncated
```

失真。

最终 Quota Authority 应继续属于：

```text
ToolExecutionSpec.max_output_bytes
```

------

## Q12：Exactly-once 怎么做到的？

```text
Approval
→ Claim
→ CAS
→ Execution
```

duplicate approval 无法获得第二次 Execution Claim。

------

## Q13：为什么 GitHub MCP writable 仍然需要 Local HITL？

因为：

```text
Provider 能做
```

和：

```text
Runtime 允许做
```

是两个不同问题。

------

## Q14：为什么 HTTP 403 被归为 Auth Configuration，而不是 MCP Bug？

因为：

```text
Tool discovered
Schema correct
Arguments correct
Governance correct
Execution reached provider
```

最终 GitHub 明确：

```text
Permission denied
```

------

## Q15：为什么 external count=0 不能直接说没执行？

因为：

```text
Read-side Visibility
```

可能有延迟。

------

# 70. 高频面试追问

## MCP 和 Function Calling 有什么区别？

Function Calling：

```text
Model → 表达 Tool Call
```

MCP：

```text
Host ↔ External Tool Provider
```

在我的系统中：

```text
DeepSeek Native Function Calling
→ MCP-backed Tool
→ Runtime
→ MCP Server
```

二者不是替代关系。

------

## MCP 和 Plugin 有什么区别？

MCP 更偏：

```text
标准化 Client / Server Protocol
```

Plugin 更偏：

```text
产品级 Integration Packaging
```

Plugin 可以内部使用 MCP，也可以不用。

------

## MCP 是否负责权限管理？

协议可以携带能力和 Metadata，

但我的 Runtime 不把：

```text
Provider Metadata
```

当 Security Authority。

真正权限仍由：

```text
Local Governance
```

决定。

------

## MCP 能不能保证 Exactly-once？

不能。

Exactly-once 来自：

```text
Runtime Claim / CAS
```

------

## MCP timeout 能不能 retry？

Read-only 可以根据 Runtime Policy 判断。

Non-idempotent Mutation 如果状态 UNKNOWN：

```text
不能安全自动 retry
```

------

## MCP Server 返回错误意味着没有执行吗？

不能这样判断。

尤其 Mutation：

```text
provider_started=true
```

以后：

```text
isError
timeout
connection drop
```

都可能对应 UNKNOWN。

------

## 你为什么需要 GitHub Official MCP Server？

为了证明：

```text
Cross-implementation Interoperability
```

而不是只证明：

```text
自己的 Client 和自己的 Server 能通信
```

------

# 71. Phase9 30 秒背诵版

> Phase9 我给 LocalAgent 增加了 MCP Integration，但没有重新做第二套 Tool Runtime。MCP Server 只作为 External Tool Provider，通过 MCP-backed ToolAdapter 注册进现有 ToolRegistry，继续复用 Typed Validation、Governance、HITL、Claim/CAS 和 ToolExecutionService。Client 采用 application-scope stdio session 和 startup snapshot discovery，本地 canonical identity 与 remote MCP identity 分离，MCP annotations 不能覆盖本地 Risk Policy。之后我做了真实 DeepSeek + MCP + HITL E2E，并进一步接入 GitHub 官方 MCP Server证明跨实现兼容。过程中发现 GitHub `get_file_contents` 使用 EmbeddedResource 返回正文，所以只扩展了标准 Tool Result 的 Embedded Text 支持，没有扩成完整 Resources。最终还用 GitHub `issue_write` 验证了真实 mutation：APPROVE 创建一个 Issue、duplicate APPROVE 仍只执行一次、REJECT 则完全零执行。

------

# 72. Phase9 2 分钟项目叙事

> LocalAgent 在 MCP 之前已经有比较完整的 Tool Runtime，包括 Registry、Typed ToolInvocation、Validation、Governance、HITL、Claim/CAS 和 ToolExecutionService，所以我在设计 MCP 时最重要的原则就是不能重新做第二套 Runtime。MCP 只作为 External Tool Provider，通过一个 MCP-backed ToolAdapter 进入现有执行链。
>
> 架构阶段我先冻结了几个关键 Owner：MCP Client 和 Session 是 application scope；Tool Discovery 只在启动阶段做 immutable snapshot；remote server/tool identity 和 Runtime canonical identity 分离；MCP annotations 只作为 Provider Claim，本地 ToolPolicy 仍然是 Risk 和 Approval Authority；timeout、cancellation 和 retry Owner 仍然属于 Runtime。
>
> 实现上先做 stdio MCP Client、initialize 和 tools/list，然后把发现的 Tool 经过 operator mapping 注册进 Existing ToolRegistry。执行仍然经过 Validation、Governance 和 ToolExecutionService，MCP Client 自己不能自动 retry mutation。
>
> 之后我做了真实 Protocol E2E，用独立 MCP subprocess 加真实 DeepSeek 验证 read-only、APPROVE 和 REJECT。这里还遇到一个真实 DeepSeek Tool Call message 的 content 可以为 None，修了 token estimation 的 nullability bug。
>
> 原 Phase9 Final Gate 虽然已经通过，但我没有声称 third-party interoperability，因为 Server 还是自己实现的。所以又接了 GitHub 官方 MCP Server。第一次 `get_file_contents` 失败，因为 GitHub 把真正正文放在标准 EmbeddedResource 里，而我原来只支持 TextContent。我没有写 GitHub 特判，而是做了一个很窄的 result normalization Architecture Reopen，只支持 EmbeddedResource 的 TextResourceContents，不做完整 Resources。
>
> 最后 read-only 官方 GitHub E2E 跑通后，我又使用 `issue_write(method=create)` 验证真实 side effect。这个 Tool 在本地被分类成 HIGH / APPROVAL_REQUIRED，Real DeepSeek 从自然语言选择 Tool，APPROVE 后真实创建 GitHub Issue，同一 approval 重复 APPROVE 仍只有一次 MCP execution 和一个 Issue；REJECT 则 TOOL_STARTED、MCP call 和 GitHub side effect 全部为零。最终证明 MCP 只是 Provider，真正的安全、Exactly-once 和 Side-effect Truth 仍然属于 LocalAgent Runtime。

------

# 73. 最值得背的 15 句话

1. **MCP 是 External Tool Provider Protocol，不是第二套 Tool Runtime。**
2. **MCP-backed Tool 必须进入 Existing Registry / Governance / Execution Chain。**
3. **MCP metadata 是 Provider Claim，不是 Runtime Security Authority。**
4. **Remote Tool Identity 与 Local Canonical Identity 必须分离。**
5. **Tool Registration 必须与 Local Policy Coverage 一起成立。**
6. **Startup Snapshot 用动态能力换 Determinism 和 Security。**
7. **MCP Client 不拥有 Retry Authority。**
8. **Timeout 表示 Execution Uncertainty，不表示没有执行。**
9. **Side-effect Truth 和 Result Decoding 必须分开。**
10. **Exactly-once 来自 Approval + Claim + CAS，不来自 MCP。**
11. **EmbeddedResource in tools/call 不等于实现 MCP Resources Primitive。**
12. **Cross-implementation interoperability 必须用外部实现证明。**
13. **Account Permission 不等于 Credential Scope。**
14. **Mutation Target Identity 不能靠 Agent 猜。**
15. **一次外部 Read Observation 为 0，不足以覆盖 Runtime 的 UNKNOWN Side-effect Truth。**

------

# 74. Truth / Completion Boundary

## 已真实实现

```text
Stdio MCP Client
Application-scope MCP lifecycle

MCP 2025-06-18 initialize
initialized notification

paginated tools/list
Startup immutable discovery snapshot

MCP-backed ToolAdapter

Operator Local Mapping
Canonical local identity
Tool registration
Local policy coverage

MCP tools/call

TextContent result
EmbeddedResource(TextResourceContents)

isError handling

Existing Governance reuse
Existing HITL reuse
Existing Claim/CAS reuse
Existing ToolExecutionService reuse

Runtime timeout/cancel/retry ownership reuse
```

------

# 75. 已真实测试

```text
Deterministic MCP Client tests
Discovery tests
Registration tests
Governance tests
Side-effect semantics tests

Real independent MCP subprocess

Real MCP Protocol E2E

Real DeepSeek tool selection

Real role=tool continuation

Real APPROVE HITL

Real REJECT HITL

Demo mutation exactly-once
Demo reject zero-execution

GitHub Official MCP initialize

GitHub Official tools/list

GitHub Official get_file_contents

GitHub EmbeddedResource text

GitHub Real Final Answer continuation

GitHub Official issue_write(method=create)

GitHub HIGH / APPROVAL_REQUIRED

GitHub Real HTTP APPROVE

GitHub duplicate APPROVE

GitHub External Issue count = 1

GitHub REJECT

GitHub External Issue count = 0
```

最终：

```ini
CROSS_IMPLEMENTATION_MCP_INTEROP = PASS

GITHUB_MUTATION_EXACTLY_ONCE = PASS

GITHUB_REJECT_ZERO_EXECUTION = PASS

REAL_GITHUB_MCP_MUTATION_E2E = PASS

REAL_HITL_GITHUB_MCP_E2E = PASS
```

------

# 76. 仍未实现

```text
Streamable HTTP

SSE legacy transport support

MCP Resources primitive
resources/list
resources/read
resources/subscribe

MCP Prompts

ResourceLink

BlobResourceContents

ImageContent

AudioContent

structured-only Tool Result

task-augmented result

runtime listChanged

dynamic tool refresh

hot reload

automatic reconnect

reconnect-and-replay

generic OAuth framework

MCP Marketplace

Tool RAG

Tool Embedding Retrieval

Generic Plugin Framework

all GitHub Tool support

all MCP Server compatibility

A2A
```

------

# 77. Accepted Limitations

当前仍应主动承认：

### 1. Transport

```text
stdio only
```

没有 Streamable HTTP。

### 2. Result subset

只支持：

```text
TextContent
EmbeddedResource(TextResourceContents)
```

不支持完整 ContentBlock universe。

### 3. Resource

没有：

```text
Resources Primitive
```

### 4. Session recovery

timeout 后：

```text
session broken
fail closed
```

没有自动 reconnect/replay。

### 5. Schema

仍是：

```text
bounded JSON Schema subset
```

不是完整 JSON Schema implementation。

### 6. Dynamic discovery

没有：

```text
listChanged
hot reload
```

### 7. Cross-implementation coverage

真实验证了：

```text
GitHub Official MCP Server
```

但不能宣称：

```text
all MCP servers compatible
```

### 8. GitHub mutation coverage

真实验证的是：

```text
issue_write(method=create)
```

不能宣称：

```text
所有 GitHub mutation tool
```

------

# 78. 面试时不要说错的地方

不要说：

```text
“MCP 保证 exactly-once”
```

应该说：

```text
“Exactly-once 是 Runtime Claim/CAS 保证的。”
```

------

不要说：

```text
“我实现了 MCP Resources”
```

应该说：

```text
“我支持 Tool Result 中 Embedded Text Resource，
但 Resources Primitive 仍未实现。”
```

------

不要说：

```text
“支持全部第三方 MCP Server”
```

应该说：

```text
“已经和 GitHub 官方 MCP Server 做过真实跨实现验证。”
```

------

不要说：

```text
“MCP annotations 决定工具风险”
```

应该说：

```text
“annotations 是 Provider Claim，
Local Policy 才是 Authority。”
```

------

不要说：

```text
“Provider 报错就意味着没执行”
```

应该说：

```text
“Mutation provider_started 后发生异常，
Side-effect Truth 可能只能是 UNKNOWN。”
```

------

不要说：

```text
“GitHub 403 是我的 MCP Schema Bug”
```

真实情况是：

```text
Arguments 正确
Schema 正确
GitHub 返回权限拒绝
→ AUTH_CONFIGURATION_FAILURE
```

------

# 79. Phase9 的工程价值

Phase9 最终不是简单完成：

```text
MCP Client
```

而是建立了：

```text
External Tool Provider
        ↓
Protocol Adapter
        ↓
Unified Runtime Safety
```

这意味着未来：

```text
GitHub MCP
Filesystem MCP
Database MCP
Internal Company MCP
```

理论上都不应该重新实现：

```text
Governance
Approval
Claim
Retry
Side-effect Tracking
```

只需要：

```text
Provider Connection
Discovery
Mapping
Adapter
```

这才是 MCP Integration 真正的工程价值。

------

# 80. Phase9 最终面试评价

Phase9 目前已经足够支撑较深入的 AI Agent / Agent Runtime 面试。

可以真实讨论：

```text
MCP Client / Server

Tool Discovery

stdio lifecycle

JSON-RPC

Capability Negotiation

Tool Identity

Namespace

Provider Metadata Trust

ToolAdapter / Anti-Corruption Layer

Local Governance

HITL

Approval Binding

Claim / CAS

Exactly-once

Zero-execution

Idempotency

Retry Authority

Side-effect Truth

Timeout / Cancellation

Protocol Compatibility

EmbeddedResource

Cross-implementation Interoperability

Credential Scope

Failure Attribution

Secret Boundary
```

而且这些不只是八股概念，大部分都能够对应到：

```text
真实源码设计
真实 deterministic regression
真实 DeepSeek
真实 MCP subprocess
真实 GitHub official server
真实 GitHub side effect
真实 Bad Case
```

因此 Phase9 的完整项目叙事可以收束为：

> **我没有把 MCP 当成另一个工具执行框架，而是把它设计成 LocalAgent 现有 Tool Runtime 的外部 Provider 接入层。先冻结 Client、Session、Identity、Governance、Timeout、Retry 和 Result 的 Owner，再通过 Adapter 把 MCP Tool 注册进现有 Runtime。随后不仅完成自建标准 MCP Server 的真实协议 E2E，还接入 GitHub 官方 MCP Server 做跨实现验证；过程中根据真实 EmbeddedResource compatibility gap 扩展标准 Tool Result 子集，最后用 GitHub `issue_write` 验证第三方真实 Side Effect 仍受 Local Governance/HITL 控制，并通过 Runtime Claim/CAS 与 GitHub 外部状态共同证明 Exactly-once 和 Reject Zero-execution。**