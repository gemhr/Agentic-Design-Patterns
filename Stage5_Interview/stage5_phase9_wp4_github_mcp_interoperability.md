# Stage5-Phase9-WP4 — GitHub Official MCP Interoperability 学习 / 面试总结

推荐文件名：

```text
docs/interview/github_mcp_interoperability.md
```

------

# 1. 本 WP 解决了什么问题

Phase9 原本已经完成了：

```text
LocalAgent
→ MCP Client
→ MCP Discovery
→ MCP-backed ToolAdapter
→ Existing ToolRegistry
→ Governance
→ ToolExecutionService
```

并且通过自建的独立 `mcp_demo_server.py` 做过真实 MCP Protocol E2E。

但当时仍有一个重要 Truth Boundary：

```ini
REAL_MCP_PROTOCOL_E2E = PASS
CROSS_IMPLEMENTATION_MCP_INTEROP = NOT_PROVEN
```

原因是：

> Demo Server 虽然独立进程、真实 stdio、真实 JSON-RPC，但仍然是 LocalAgent 项目自己实现的 MCP Server。

WP4 的目标就是把这个缺口补掉：

> 使用 GitHub 官方 `github-mcp-server`，验证 LocalAgent 是否真的能够兼容一个外部官方 MCP implementation。

最终不仅完成了 read-only：

```text
get_file_contents
```

还继续完成了 mutation：

```text
issue_write(method=create)
```

以及：

```text
APPROVE exactly-once
REJECT zero-execution
```

最终：

```ini
GITHUB_OFFICIAL_MCP_INTEROP = PASS
CROSS_IMPLEMENTATION_MCP_INTEROP = PASS

REAL_GITHUB_MCP_MUTATION_E2E = PASS
REAL_HITL_GITHUB_MCP_E2E = PASS
```

------

# 2. WP4 最终真实架构

最终链路并没有因为 GitHub 增加第二套 Runtime。

真实结构仍然是：

```text
GitHub Official MCP Server
        │
        │ stdio / MCP 2025-06-18
        ▼
Existing StdioMcpClient
        │
        ▼
McpIntegrationComponent
        │
        ├── initialize
        ├── tools/list
        └── tools/call
        │
        ▼
McpDiscoverySnapshot
        │
        ▼
Operator Local Mapping
        │
        ▼
McpBackedToolAdapter
        │
        ▼
Existing ToolRegistry
        │
        ▼
Existing ToolPolicy / Governance
        │
        ├── ALLOW
        └── APPROVAL_REQUIRED
        │
        ▼
Existing ToolApprovalController
        │
        ▼
Execution Claim / CAS
        │
        ▼
Existing ToolExecutionService
        │
        ▼
GitHub Official MCP tools/call
```

整个 WP4 都没有增加：

```text
GitHubRuntime
GitHubGovernance
GitHubExecutor
GitHubApprovalController
GitHub-specific ToolInvocation
```

最终 mutation 验证也没有修改这些 Owner。

------

# 3. Read-only Cross-Implementation E2E

第一部分验证的是：

```text
github-mcp-server
→ get_file_contents
```

LocalAgent 只暴露：

```text
remote_name = get_file_contents
local_name  = github_get_file_contents
```

然后：

```text
自然语言
→ Real DeepSeek
→ github_get_file_contents
→ Local Governance ALLOW
→ ToolExecutionService
→ GitHub Official MCP
→ README.md
→ role=tool
→ Final Answer
```

真实证明：

```ini
REAL_GITHUB_MCP_E2E = PASS
REAL_REMOTE_MODEL_GITHUB_MCP_E2E = PASS
GITHUB_FINAL_TOOL_CONTINUATION = PASS

GITHUB_OFFICIAL_MCP_INTEROP = PASS
CROSS_IMPLEMENTATION_MCP_INTEROP = PASS
```

并且 Final Answer 确实使用了 README 正文，而不是仅根据“下载成功”状态生成答案。

------

# 4. 第一个重要工程发现：EmbeddedResource

GitHub 官方：

```text
get_file_contents
```

第一次执行时并没有直接成功。

GitHub 返回的 `CallToolResult.content` 实际类似：

```text
TextContent
+
EmbeddedResource
    └── TextResourceContents
```

其中：

```text
TextContent
```

主要是状态说明，

真正 README 正文位于：

```text
EmbeddedResource.resource.text
```

而 Phase9 原来的冻结策略只支持：

```text
TEXT_CONTENT_AND_ISERROR_ONLY
```

因此真实 GitHub E2E 第一次失败：

```text
MCP_TOOL_RESULT_UNSUPPORTED
```

这不是 GitHub-specific bug，而是：

> LocalAgent 支持的标准 MCP `CallToolResult` 子集过窄。

------

# 5. 为什么这需要 Architecture Reopen

当时不能直接写一个：

```python
if server_id == "github":
    return resource["text"]
```

因为这会变成：

```text
GitHub-specific hack
```

而不是 MCP compatibility。

于是进行了一个非常窄的 Architecture Reopen：

```ini
REOPEN_SCOPE =
MCP_CALL_TOOL_RESULT_NORMALIZATION_ONLY
```

批准：

```text
TextContent
+
EmbeddedResource(TextResourceContents)
+
isError
```

继续拒绝：

```text
BlobResourceContents
ResourceLink
Image
Audio
structured-only
task result
```

同时明确：

```ini
TOOLS_ONLY_FOR_PHASE9 = YES
MCP_RESOURCES_PRIMITIVE_REQUIRED = NO
```

------

# 6. EmbeddedResource ≠ MCP Resources Primitive

这是本 WP 非常值得面试讲的一点。

两个概念完全不同。

## Tool Result Embedded Resource

```text
tools/call
   ↓
CallToolResult.content[]
   ↓
EmbeddedResource
   ↓
resource.text
```

数据已经随着这次 Tool Call 返回。

因此只需要：

```text
读取 embedded text
→ normalize
```

不需要第二次外部 I/O。

------

## MCP Resources Primitive

另外一套能力是：

```text
resources/list
resources/read
resources/subscribe
```

这是资源发现、读取、订阅的独立 MCP Primitive。

WP4 没有实现。

因此：

```text
支持 tools/call 里的 EmbeddedResource
```

不能说成：

```text
LocalAgent 支持 MCP Resources
```

这是一个非常重要的 Truth Boundary。

------

# 7. Embedded Text 最终是怎么处理的

Production 最终只需要修改：

```text
mcp/models.py
```

`mcp/adapter.py` 原来的：

```text
content parts
→ "\n".join(...)
```

逻辑可以继续直接复用。

最终支持：

```text
TextContent.text
EmbeddedResource.resource.text
```

按 Content Array 原始顺序：

```text
Text
Resource
Text
Resource
```

归一化成：

```text
text
resource text
text
resource text
```

不：

```text
strip
排序
去重
插入 URI
插入 MIME
插入 metadata
```

------

# 8. URI 为什么只校验、不访问

Embedded Resource 中还有：

```text
uri
mimeType
annotations
_meta
```

但是 WP4 的设计是：

```text
uri
→ structural validation
→ discard
```

明确禁止：

```text
URI
→ HTTP fetch

URI
→ filesystem read

URI
→ resources/read
```

因为正文已经：

```text
embedded
```

无需再次访问。

这避免了一个非常危险的设计扩张：

```text
Tool Result
→ URI
→ 第二次外部网络访问
```

否则 Runtime 又会遇到：

```text
新的 timeout
新的 cancellation
新的 authorization
新的 side effect
新的 retry
新的 lifecycle
```

Owner 问题。

------

# 9. Output Size 为什么不在 MCP Adapter 再加一套

另一个重要设计：

没有新增：

```text
MCP_EMBEDDED_RESOURCE_MAX_BYTES
```

当前仍然：

```text
MCP stdio wire
    │
    │ 1 MiB framing bound
    ▼
McpToolCallResult
    ▼
normalized text
    ▼
ToolExecutionService
    ▼
ToolExecutionSpec.max_output_bytes
    ▼
ToolOutput
```

唯一最终 Output Authority 仍然是：

```text
ToolExecutionSpec.max_output_bytes
```

这样已有：

```text
original_size_bytes
returned_size_bytes
truncated
digest
```

语义不被破坏。

如果在 Adapter 提前 truncate：

```text
original_size
digest
```

就不再代表 Provider 的完整 normalized output。

WP4 保持了这一边界。

------

# 10. Mutation 为什么比 Read-only 更有价值

Read-only 只能证明：

```text
第三方 MCP Tool
→ 可以发现
→ 可以执行
→ 可以返回结果
```

Mutation 进一步验证了：

> 外部 MCP Tool 即使具有真实副作用，也不会绕过 LocalAgent Runtime Safety。

本轮使用：

```text
GitHub official issue_write
method=create
```

映射：

```text
remote_name = issue_write
local_name  = github_issue_write
```

Local Policy：

```text
LOCAL_STATE_MUTATION
+
NON_IDEMPOTENT
```

得到：

```text
HIGH
→ APPROVAL_REQUIRED
```

实际 discovery、registration 和 Governance 均通过。

------

# 11. GitHub Server writable ≠ 自动允许执行

Mutation E2E 中 GitHub Server 必须关闭：

```text
GITHUB_READ_ONLY=1
```

否则 `issue_write` 根本不会暴露。

但 GitHub MCP Server writable 只表示：

```text
Provider 可以执行 mutation
```

不表示：

```text
LocalAgent 允许执行 mutation
```

真正安全链仍是：

```text
Provider capability
        ↓
Local Tool Policy
        ↓
ToolGovernanceService
        ↓
APPROVAL_REQUIRED
```

所以面试时可以说：

> MCP Server 声明自己能写，不等于 Runtime 就允许写；Provider Capability 和 Runtime Authorization 是两个完全不同的 Authority。

------

# 12. APPROVE 完整真实链

最终成功 Run：

```text
run_id =
d5638eedc86c46feb00a72e77676fc50
```

Real DeepSeek 收到自然语言：

```text
创建一个测试 Issue
```

用户请求没有显式指定：

```text
github_issue_write
issue_write
method=create
JSON arguments
```

DeepSeek 自己选择：

```text
github_issue_write
```

随后：

```text
risk_level = HIGH
↓
TOOL_APPROVAL_REQUESTED
↓
HTTP APPROVE
↓
Execution Claim
↓
ToolExecutionService
↓
GitHub Official MCP issue_write
↓
GitHub Issue #1
```

------

# 13. Exactly-once 是怎么证明的

第一次：

```text
HTTP APPROVE
→ 200
→ idempotent=false
```

第二次对相同：

```text
run_id
approval_id
```

再次 APPROVE：

```text
HTTP 200
→ idempotent=true
```

但关键不是 HTTP 返回值。

内部证据：

```text
TOOL_STARTED = 1
TOOL_COMPLETED = 1
MCP execution = 1
```

外部 GitHub 证据：

```text
unique marker Issue count = 1
```

最终：

```ini
GITHUB_MUTATION_MCP_CALL_COUNT = 1
GITHUB_MUTATION_CREATED_ISSUE_COUNT = 1

GITHUB_DUPLICATE_APPROVE_MCP_CALL_COUNT = 1
GITHUB_DUPLICATE_APPROVE_CREATED_ISSUE_COUNT = 1

GITHUB_MUTATION_EXACTLY_ONCE = PASS
```

------

# 14. Exactly-once 不是 MCP 提供的

这是面试必须强调的。

不是：

```text
MCP guarantees exactly-once
```

而是：

```text
Approval
+
Execution Claim
+
CAS
```

保证：

```text
相同 approval
→ 只有一个 execution owner
```

然后：

```text
ToolExecutionService
→ MCP Adapter
→ GitHub MCP
```

所以 exactly-once：

```text
是在 LocalAgent Runtime 层实现
```

MCP 只是：

```text
Transport / Provider protocol
```

这与 Phase7/Phase8 的设计完全衔接。

------

# 15. REJECT Zero-execution

独立 REJECT Run：

```text
run_id =
5285f7ca7e9343879c3da96c6788cdc9
```

执行：

```text
Natural language
→ github_issue_write
→ APPROVAL_REQUIRED
→ HTTP REJECT
```

最终：

```text
TOOL_STARTED = 0
TOOL_COMPLETED = 0
MCP call = 0
GitHub Issue count = 0
```

因此：

```ini
GITHUB_REJECT_ZERO_EXECUTION = PASS
```

这比只看 Runtime 状态更强，因为 GitHub 外部状态也证明：

```text
没有发生真实副作用
```

------

# 16. Side-effect Truth 为什么重要

Mutation 最容易出错的是：

```text
Provider 调用失败
```

不等于：

```text
副作用一定没发生
```

例如：

```text
HTTP request sent
↓
GitHub 创建 Issue
↓
response connection lost
```

Runtime 看到的是：

```text
timeout
```

但真实副作用可能已经发生。

因此 LocalAgent 的语义：

```text
mutation success
→ COMMITTED

timeout after provider_started
→ UNKNOWN

isError after mutation boundary
→ UNKNOWN

unsupported result after protocol success
→ COMMITTED + result failure
```

这是典型的：

> Side-effect Truth（副作用事实）和 Result Observation（结果观察）分离。

------

# 17. 为什么 UNKNOWN 不能自动 Retry

WP4 中第一次真实 mutation 曾经收到：

```text
MCP_TOOL_REPORTED_ERROR
SIDE_EFFECT_UNKNOWN
```

当时 GitHub observation 是：

```text
Issue count = 0
```

但 Runtime 没有因此自动：

```text
UNKNOWN → NOT_STARTED
```

也没有自动重新调用。

这是正确行为。

因为：

```text
GitHub 当前查不到
```

只是一个后续 observation，

不能逻辑上证明：

```text
之前的 mutation 一定没有发生
```

尤其分布式系统可能存在：

```text
写入成功
读侧延迟
eventual visibility
```

------

# 18. 本 WP 真实观察到的 GitHub Read-side Delay

最终成功 Run 中：

```text
GitHub issue_write
→ LocalAgent succeeded
```

流刚结束时第一次 REST observation：

```text
count = 0
```

随后再次独立 observation：

```text
count = 1
```

并找到：

```text
Issue #1
```

报告将其记录为：

> GitHub read-side 短暂可见性延迟。

这也是为什么：

```text
一次 GET 没查到
```

不能轻易作为：

```text
mutation 未发生
```

的绝对证据。

------

# 19. Bad Case 1 — 自建 MCP E2E 不能证明第三方互操作

## Truth Source

Phase9 Final Gate / WP4。

## Trigger

只有：

```text
LocalAgent
→ 自建 mcp_demo_server
```

## Symptom

Protocol E2E PASS，但：

```text
CROSS_IMPLEMENTATION_MCP_INTEROP = NOT_PROVEN
```

## Risk

面试中声称：

```text
“支持任意 MCP Server”
```

但实际只测试过自己的实现。

## Root Cause

测试双方：

```text
Client
Server
```

都由自己控制。

## Fix

接入：

```text
GitHub Official MCP Server
```

## Regression

```text
initialize
tools/list
tools/call
Real DeepSeek
Final Answer
```

全部真实验证。

## Knowledge Point

```text
Protocol E2E
≠
Cross-implementation Interoperability
```

------

# 20. Bad Case 2 — Text-only Client 无法消费 GitHub get_file_contents

## Truth Source

REAL_GITHUB_MCP_E2E。

## Trigger

GitHub：

```text
get_file_contents
```

## Symptom

```text
MCP_TOOL_RESULT_UNSUPPORTED
```

## Root Cause

正文位于：

```text
EmbeddedResource.resource.text
```

而 Client 只支持：

```text
TextContent
```

## Risk

看似：

```text
tools/call success
```

但客户端拿不到真正业务数据。

## Fix

Architecture Reopen：

```text
TextContent
+
EmbeddedResource(TextResourceContents)
```

## Regression

GitHub README 正文真正进入：

```text
ToolOutput
→ role=tool
→ Final Answer
```

## Knowledge Point

> MCP Client 必须明确自己的 supported content subset。

------

# 21. Bad Case 3 — GitHub-specific Parser Hack

## 类型

HYPOTHETICAL_BAD_CASE

## 错误实现

```python
if server_id == "github":
    return result["resource"]["text"]
```

## 风险

Provider lock-in：

```text
GitHub 特判
GitLab 再特判
Filesystem 再特判
```

最终失去 MCP Adapter 的协议抽象意义。

## 正确方法

按照：

```text
MCP ContentBlock type
```

进行通用处理。

------

# 22. Bad Case 4 — Embedded URI 自动 Fetch

## 类型

HYPOTHETICAL_BAD_CASE

## 错误实现

```text
EmbeddedResource.uri
→ 自动 HTTP GET / resources.read
```

## 风险

引入：

```text
新的 network I/O
新的 timeout
新的 retry
新的 security
新的 lifecycle
```

## 正确方法

如果：

```text
resource.text
```

已经 embedded：

```text
validate URI
→ do not fetch
→ use embedded text
```

------

# 23. Bad Case 5 — localhost 请求被代理导致 502

## Truth Source

真实 harness 运行。

## Trigger

临时 HTTP Client 继承系统 Proxy Environment。

## Symptom

访问：

```text
loopback /api/chat
```

返回：

```text
HTTP 502
```

请求甚至没有进入 LocalAgent。

## Root Cause

临时 E2E harness：

```text
trust_env=true
```

导致 localhost 请求误走代理。

## Fix

Harness-only：

```text
trust_env=false
```

没有修改 production code。

## Knowledge Point

> E2E Failure 不一定是业务系统 Failure，要先区分 Harness / Environment / Runtime / Provider。

------

# 24. Bad Case 6 — Owner 配置拼写错误

## Truth Source

真实 WP4 Environment Check。

错误：

```text
gemhrrr
```

真实：

```text
gemhr
```

导致：

```text
configured repo → HTTP 404
provided link → PASS
```

系统没有自动把：

```text
gemhrrr
```

偷偷修成：

```text
gemhr
```

而是：

```text
fail closed
```

这体现：

> Mutation Target Identity 不能由 Agent 猜测。

------

# 25. Bad Case 7 — PAT 有 Repo 权限但没有 Issues Write

## Truth Source

真实 GitHub official mutation。

## Trigger

```text
issue_write(method=create)
```

## Symptom

GitHub official provider 返回：

```text
HTTP 403
```

## 进一步诊断

实际 Model Arguments：

```text
method=create
owner=gemhr
repo=localagent-mcp-test
title_present=true
body_present=true
```

因此排除了：

```text
MODEL_ARGUMENT_CONSTRUCTION
MCP_SCHEMA_COMPATIBILITY
```

最终定性：

```text
AUTH_CONFIGURATION_FAILURE
```

## Knowledge Point

> Account 对仓库有权限，不等于当前 Credential / PAT 拥有相同权限。

这是：

```text
Principal Permission
```

和：

```text
Credential Scope
```

的区别。

------

# 26. Bad Case 8 — Provider Error 后自动 Retry mutation

## 类型

真实风险，WP4 实际避免。

## 场景

第一次：

```text
issue_write
→ HTTP 403
→ SIDE_EFFECT_UNKNOWN
```

错误实现：

```text
“没看到 Issue”
→ retry
```

## 风险

如果 Provider 实际已经提交副作用但 response 失败：

```text
retry
→ duplicate Issue
```

## 正确行为

```text
UNKNOWN
→ no automatic retry
```

只能：

```text
用户显式授权全新 Run
+
全新 marker
```

再执行。

最终成功 Run 就是这种形式。

------

# 27. Bad Case 9 — 用一次立即查询 0 判断写入失败

## Truth Source

真实最终 Run。

实际：

```text
issue_write succeeded
↓
immediate REST count = 0
↓
later observation count = 1
```

## 错误结论

```text
count=0
→ mutation definitely failed
```

## 正确理解

External Observation 和 Execution Truth 是不同证据。

应该结合：

```text
Runtime completion
Provider result
Claim/CAS
External eventual state
```

综合判断。

------

# 28. 名词 / 概念速览

### Cross-implementation Interoperability（跨实现互操作）

两个由不同实现方开发的 MCP Client / Server 能按标准协议正确通信。

### MCP Host（MCP 宿主）

拥有 MCP Client 并消费 MCP Server 能力的应用；LocalAgent 在本项目里属于 Host。

### MCP Server（MCP 服务端）

通过 MCP 暴露 Tool / Resource / Prompt 等能力的外部 Provider。

### Tool Provider（工具提供方）

真正提供工具能力的一方；GitHub MCP 是 External Tool Provider。

### Canonical Tool Name（规范工具名）

Runtime 内部唯一稳定 Tool Identity，如 `github_issue_write`。

### Remote Tool Name（远端工具名）

MCP Server 暴露的原始名称，如 `issue_write`。

### EmbeddedResource（内嵌资源）

直接包含在 MCP Tool Result ContentBlock 中的 Resource。

### TextResourceContents（文本资源内容）

EmbeddedResource 中携带 `text` 字段的文本型资源。

### Resources Primitive（资源原语）

MCP 的 `resources/list`、`resources/read`、订阅等资源能力。

### Governance Authority（治理权威）

决定 Tool 是否允许执行、是否需要审批的本地 Runtime Owner。

### Provider Metadata（提供方元数据）

MCP Server 对 Tool 的描述或 annotations，只作为外部声明，不能自动成为安全事实。

### HITL — Human-in-the-loop（人在回路）

高风险动作执行前需要人工显式 APPROVE / REJECT。

### Claim（执行认领）

Runtime 对一个 execution 取得唯一执行权。

### CAS — Compare-And-Set（比较并设置）

用于并发安全地把状态从预期旧值原子更新成新值。

### Exactly-once（恰好一次）

同一个逻辑批准最终只触发一次真实 execution。

### Zero-execution（零执行）

REJECT 后没有任何实际 Provider execution。

### Side-effect Truth（副作用事实）

Runtime 对外部副作用处于 NOT_STARTED / COMMITTED / UNKNOWN 等真实状态判断。

### Idempotency（幂等性）

同一操作重复执行是否仍等价于执行一次。

### Retry Authority（重试权威）

决定是否允许重新执行 Tool 的唯一 Runtime Owner。

### Fail Closed（失败关闭）

无法明确证明安全时拒绝继续，而不是默认放行。

### Provider Permission（提供方权限）

GitHub PAT 等 Credential 对实际远端资源拥有的权限。

### Credential Scope（凭证权限范围）

Token 自身被授权的能力范围，与账号本身权限不同。

------

# 29. 工程方法类面试问答

## Q1：为什么 MCP Tool 不能绕过现有 Tool Runtime？

因为 MCP 只是：

```text
External Tool Provider
```

如果 MCP 自己：

```text
validation
governance
approval
execution
retry
```

就会形成第二套 Runtime。

这样同一个系统里会出现：

```text
Local Tool
→ Runtime A

MCP Tool
→ Runtime B
```

安全语义无法统一。

我的设计是：

```text
MCP
→ Adapter
→ Existing Runtime
```

而不是：

```text
Runtime
→ MCP Runtime
```

------

## Q2：为什么 MCP annotations 不能决定 Risk？

因为 annotations 来自：

```text
Remote Provider
```

属于：

```text
Provider Claim
```

而不是：

```text
Runtime Fact
```

例如 Server 声称：

```text
readOnlyHint=true
```

LocalAgent 仍然要以：

```text
Local ToolPolicy
```

判断：

```text
Side effect
Risk
Idempotency
Approval
```

------

## Q3：为什么 Remote Name 和 Local Name 要分开？

例如：

```text
remote:
issue_write

local:
github_issue_write
```

因为：

```text
remote_name
```

只是 Provider Namespace。

Runtime 的：

```text
Policy
Journal
Evaluation
Governance
ToolInvocation
```

需要稳定、本地可控的 Identity。

否则两个 MCP Server 都暴露：

```text
read_file
```

就会 collision。

------

## Q4：为什么 ToolRegistration 和 Policy 要一起成功？

因为如果：

```text
Tool registered
但 Policy 没有
```

Model 已经能看到 Tool，但 Runtime 无法正确判断风险。

这是：

```text
Security Coverage Hole
```

所以当前设计是：

```text
Discovery
+
Mapping
+
Policy
+
Registration
```

必须满足安全覆盖后才进入 Registry Freeze。

------

## Q5：为什么启动时 Snapshot Discovery，而不是动态刷新？

当前 Phase9 目标优先：

```text
determinism
security
lifecycle simplicity
```

启动时：

```text
discover
→ validate
→ register
→ freeze
```

Runtime 执行期间 Tool Set 不变化。

代价：

```text
不支持 listChanged / hot reload
```

但大幅降低：

```text
runtime race
policy drift
tool identity drift
```

------

## Q6：为什么不实现完整 MCP Resources？

因为 GitHub 的需求只是：

```text
tools/call
→ EmbeddedResource.resource.text
```

正文已经随着 Tool Result 返回。

实现：

```text
resources/list/read/subscribe
```

会引入新的：

```text
Capability
Lifecycle
IO
Security
Caching
```

对当前目标没有必要。

------

## Q7：为什么 mutation timeout 不能自动 Retry？

因为：

```text
timeout
```

只表示 Client 没拿到可靠 Result。

不能证明：

```text
Provider 没执行
```

可能已经：

```text
GitHub create issue
```

所以：

```text
UNKNOWN
```

状态下自动 Retry 可能造成：

```text
duplicate side effect
```

------

## Q8：Exactly-once 是怎么实现的？

不是 MCP 保证。

而是：

```text
Approval Binding
→ Claim
→ CAS
→ ToolExecutionService
```

当 duplicate APPROVE 到来：

```text
Claim 已存在
→ 第二个请求 idempotent
→ 不再执行 Provider
```

GitHub 外部状态最终也证明：

```text
Issue count = 1
```

------

## Q9：为什么 REJECT 还要看 GitHub 外部状态？

因为 Runtime：

```text
TOOL_STARTED = 0
```

已经是很强证据。

但为了证明：

```text
真实 external zero execution
```

再增加：

```text
GitHub marker count = 0
```

形成独立证据面。

这是更强的 E2E Truth。

------

## Q10：为什么 403 不是 Runtime Bug？

因为诊断已经证明：

```text
method=create
owner correct
repo correct
title present
body present
```

Runtime：

```text
Discovery
Registration
Governance
Approval
Execution
```

全部成功。

Provider 最终返回：

```text
HTTP 403 Permission Denial
```

所以属于：

```text
AUTH_CONFIGURATION_FAILURE
```

------

# 30. 高频面试追问 + 简答

### 1. MCP 和 Function Calling 有什么区别？

Function Calling 更偏：

```text
模型如何表达“我要调用工具”
```

MCP 更偏：

```text
Host 与外部 Tool Provider 如何发现、描述和调用能力
```

在我的项目里二者可以同时存在：

```text
DeepSeek Native Function Calling
→ 选择 MCP-backed Tool
→ Runtime
→ MCP Server
```

------

### 2. MCP 为什么不是 Tool Runtime？

因为 MCP 定义：

```text
protocol / capability exchange / tool call
```

但不替 Runtime 决定：

```text
risk
approval
idempotency
retry
claim
side-effect truth
```

------

### 3. GitHub MCP 的写操作是谁审批？

LocalAgent。

不是 GitHub Server。

```text
GitHub MCP writable
→ Local Governance
→ APPROVAL_REQUIRED
```

------

### 4. MCP Server 自己声称 readOnly 可以信吗？

不能作为唯一安全依据。

只作为：

```text
Provider-declared metadata
```

Local policy 仍然 authoritative。

------

### 5. GitHub Issue 创建重复了怎么办？

当前 Runtime 通过：

```text
Approval Claim / CAS
```

防止 duplicate approval 导致 duplicate execution。

真实 E2E 中：

```text
duplicate approve
→ MCP call still 1
→ GitHub issue still 1
```

------

### 6. 如果 Tool 已执行但 Result parse 失败呢？

副作用 Truth 和 Result parse 分离。

例如 mutation protocol success 后：

```text
unsupported result
```

真实副作用可能已经：

```text
COMMITTED
```

不能因为结果解析失败说：

```text
NOT_STARTED
```

------

### 7. 为什么 GitHub read-only 先做？

因为先验证：

```text
Transport
Protocol
Discovery
Registration
Result compatibility
Model continuation
```

不引入真实副作用。

再在基础稳定后验证：

```text
mutation + HITL
```

降低调试复杂度。

------

### 8. 为什么不用所有 GitHub Tools 做测试？

因为目标是证明：

```text
MCP compatibility + Runtime reuse
```

不是测试 GitHub MCP 所有功能。

一个 read-only：

```text
get_file_contents
```

和一个 mutation：

```text
issue_write
```

已经覆盖最有价值的两类路径。

------

# 31. 30 秒背诵版

> 我在 LocalAgent 的 MCP Integration 完成后，又接入了 GitHub 官方 MCP Server 做跨实现验证。MCP Tool 不会绕过原有 Runtime，而是通过 McpBackedToolAdapter 进入统一的 ToolRegistry、Governance、HITL 和 ToolExecutionService。过程中发现 GitHub `get_file_contents` 会用标准 EmbeddedResource 返回正文，因此我只扩展了 tools/call 的 Embedded Text Result 支持，没有扩成完整 Resources Primitive。最终 read-only 路径真实跑通，mutation 也通过官方 `issue_write` 验证：高风险操作进入 APPROVAL_REQUIRED，APPROVE 后真实创建 GitHub Issue，重复 APPROVE 仍只有一次 MCP execution 和一个 Issue，REJECT 则 MCP 调用和 GitHub 副作用都为零。

------

# 32. 2 分钟项目叙事

> Phase9 最初虽然已经实现了 MCP Client、stdio lifecycle、startup discovery、MCP-backed ToolAdapter 和现有 Tool Runtime 的整合，也用独立 Demo Server 做过真实协议 E2E，但我没有直接声称支持第三方 MCP，因为 Client 和 Server 都是自己实现的。所以后续 WP4 专门接了 GitHub 官方 github-mcp-server 做 cross-implementation 验证。
>
> 第一阶段用 `get_file_contents` 做 read-only E2E。Transport、initialize、tools/list、registration 和 DeepSeek 自动选 Tool 都成功，但第一次 tools/call 结果失败，因为 GitHub 把真正文件正文放在标准 EmbeddedResource 的 TextResourceContents 中，而我原来的结果子集只支持 TextContent。这个问题我没有写 GitHub 特判，而是做了一个很窄的 Architecture Reopen，只扩展 MCP CallToolResult 的标准 Embedded Text Resource 支持，同时继续拒绝 Blob、ResourceLink、Image、Audio，也没有引入 resources/list 或 resources/read。最终 README 正文能通过 Existing ToolOutput 进入 role=tool continuation。
>
> 在 read-only 跨实现验证完成后，我又用 GitHub 官方 `issue_write(method=create)` 验证 mutation。GitHub MCP 只是 External Tool Provider，真正的安全 Authority 还是 LocalAgent 本地 ToolPolicy 和 Governance。这个 Tool 被映射为 NON_IDEMPOTENT mutation，因此风险为 HIGH，需要 HITL。真实测试中 DeepSeek 从自然语言自己选择 Tool，HTTP APPROVE 后 Claim/CAS 只允许一次执行，GitHub 最终确实只创建一个 Issue；对相同 approval 重复 APPROVE，MCP execution count 仍然是 1。另一个 REJECT Run 则证明 TOOL_STARTED=0、MCP call=0、GitHub Issue count=0。
>
> 这个 WP 最终证明的不只是“能调用 MCP”，而是一个第三方官方 MCP Server 可以完整进入现有 Tool Runtime，并继续复用统一的 Governance、HITL、Exactly-once 和 Side-effect Truth 语义。

------

# 33. 面试时最值得背的 10 句话

1. **MCP 是 External Tool Provider，不是第二套 Tool Runtime。**
2. **Cross-implementation interoperability 要用第三方实现证明，自建 Client + 自建 Server 不够。**
3. **MCP Provider metadata 是 Claim，不是 Runtime Security Authority。**
4. **Remote Tool Identity 和 Local Canonical Identity 必须分离。**
5. **EmbeddedResource in Tool Result 不等于实现 MCP Resources Primitive。**
6. **Timeout 代表 execution uncertainty，不代表 zero execution。**
7. **Side-effect Truth 和 Result Parsing 必须分离。**
8. **Exactly-once 来自 Approval + Claim + CAS，不来自 MCP。**
9. **REJECT zero-execution 最好同时用 Runtime event 和外部 Provider state 双重证明。**
10. **账号有 Repo 权限，不代表当前 PAT Credential 具有对应 Issues Write Scope。**

------

# 34. Truth / Completion Boundary

## 已真实实现

```text
GitHub official MCP stdio integration
get_file_contents
issue_write(method=create)

EmbeddedResource(TextResourceContents)

Local canonical mapping
Local Policy / Governance reuse
HITL reuse
Claim/CAS reuse
ToolExecutionService reuse
```

------

## 已真实验证

```text
GitHub official initialize
MCP 2025-06-18 negotiation
tools/list
tools/call

Real DeepSeek tool selection

GitHub read-only E2E
README embedded text continuation

GitHub mutation APPROVE
duplicate APPROVE
exactly-once

GitHub mutation REJECT
zero execution

external GitHub state observation
```

最终：

```ini
GITHUB_OFFICIAL_MCP_INTEROP = PASS
CROSS_IMPLEMENTATION_MCP_INTEROP = PASS

GITHUB_MUTATION_EXACTLY_ONCE = PASS
GITHUB_REJECT_ZERO_EXECUTION = PASS

REAL_GITHUB_MCP_MUTATION_E2E = PASS
REAL_HITL_GITHUB_MCP_E2E = PASS
```

------

## 仍未实现

```text
Streamable HTTP
SSE

MCP Resources primitive
resources/list
resources/read
resources/subscribe

ResourceLink support
BlobResourceContents
ImageContent
AudioContent
structured-only
task-augmented result

runtime listChanged
hot reload

automatic reconnect
reconnect-and-replay

generic OAuth framework

all GitHub write tools

all MCP implementations
```

------

# 35. 最终评价

WP4 的面试价值实际上很高，因为它把 MCP 从：

```text
“我按照协议做了一个 Client”
```

推进到了：

```text
“我的 Client 与 GitHub 官方 MCP 实现做过真实跨实现互操作”
```

再进一步推进到了：

```text
“第三方官方 MCP mutation 仍然进入我自己的 Governance / HITL / Claim / CAS，
并用 GitHub 外部真实状态证明 exactly-once 和 zero-execution。”
```

这已经足够支撑中高级 Agent 工程面试里关于：

```text
MCP
Tool Runtime
Governance
HITL
Idempotency
Exactly-once
Side-effect Truth
Protocol Compatibility
Security Boundary
Failure Attribution
```

的一整组深挖问题。