当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase9-WP2 学习 / 面试总结

## MCP-backed ToolAdapter + Existing Runtime Integration

WP2 是整个 Phase9 里**工程价值最高的一段**。

WP1 解决的是：

> LocalAgent 怎么连接 MCP Server、完成初始化并发现 Tool？

WP2 真正解决的是：

> **发现出来的 MCP Tool，怎样变成 LocalAgent Runtime 中一个“正常的 Tool”，并继续受到原有 Validation、Governance、HITL、Timeout、Cancellation、Retry、Side-effect Tracking 等机制约束？**

最终 Codex Formal Gate 已确认：

```ini
WP2_FORMAL_GATE = PASS
ARCHITECTURE_REOPEN_REQUIRED = NO
READY_FOR_WP3 = YES
```

并且 `ToolInvocation`、ToolExecution Owner、Governance Authority 均没有改变。

------

# 1. 本 WP 解决了什么问题

## 1.1 WP1 后还缺什么？

WP1 已经有：

```text
MCP Server
↓
initialize
↓
tools/list
↓
McpDiscoverySnapshot
```

但这时候 MCP Tool 只是：

> “我知道远端有这么一个 Tool。”

它还不是：

```text
LocalAgent Runtime Tool
```

还不能真正经过：

```text
ToolRegistry
ToolInvocation
Governance
HITL
ToolExecutionService
```

执行。

因此 WP2 的任务就是完成这个桥：

```text
External MCP Tool
        ↓
LocalAgent Tool
```

------

# 1.2 最终实现的真实主链

WP2 最终完成：

```text
McpDiscoverySnapshot
        ↓
Operator Local Mapping
        ↓
Canonical Local Tool Name
        ↓
MCP-backed ToolAdapter
        ↓
ToolRegistration
        +
ToolPolicy
        ↓
Existing ToolRegistry
        ↓
Existing ToolInvocation
        ↓
Existing ToolGovernanceService
        ↓
Existing HITL
        ↓
Existing ToolExecutionService
        ↓
McpBackedToolAdapter.invoke_once()
        ↓
Application-scope MCP Session
        ↓
tools/call
        ↓
Result Normalization
        ↓
Existing ToolOutput
```

也就是说：

> MCP Tool 最终不是一种新的 Runtime Tool 类型，而是一个由 MCP-backed `ToolAdapter` 驱动的普通 LocalAgent Tool。

这就是 WP2 最核心的设计。

------

# 1.3 为什么值得解决？

一种非常容易写出来的 MCP 集成是：

```python
if tool.provider == "mcp":
    mcp_client.call_tool(...)
```

然后慢慢扩展成：

```text
AgentRouter
↓
MCP Dispatcher
↓
MCP Executor
↓
MCP Retry
↓
MCP Error Handler
```

最终形成：

```text
Local Tool Runtime
+
MCP Tool Runtime
```

两套系统。

这样以前完成的：

```text
Governance
HITL
Exactly-once
Execution Claim
Retry Safety
Cancellation
Timeout
Journal
```

就可能全部失效。

而 WP2 最终 Codex 独立确认：

```text
ToolExecutionService
↓
McpBackedToolAdapter.invoke_once()
↓
client.call_tool()
```

是唯一 MCP Tool 执行路径。

------

# 2. 真实架构 / 数据流 / 状态流

## 2.1 Startup Registration Flow

WP2 的第一段发生在 application startup：

```text
McpDiscoverySnapshot
        ↓
读取 operator MCP tool mapping
        ↓
匹配 remote_name
        ↓
确定 local_name
        ↓
构造 local ToolExecutionSpec
        ↓
构造 local ToolPolicy
        ↓
构造 McpBackedToolAdapter
        ↓
构造 ToolRegistration
        ↓
验证整个 Server batch
        ↓
注入 ToolRegistry
        ↓
注入 ToolPolicyCatalog
        ↓
freeze
```

关键顺序：

```text
MCP registration
↓
ToolRegistry.freeze()
ToolPolicyCatalog.freeze()
```

而不是 freeze 以后再动态注册。

------

# 2.2 Runtime Execution Flow

真正执行时：

```text
Model
↓
选择 Local canonical tool_name
↓
ToolRegistry.require(tool_name)
↓
McpBackedToolAdapter.build_invocation()
↓
ToolInvocation
↓
adapter.spec_for()
↓
ToolGovernanceService
↓
ALLOW / DENY / APPROVAL_REQUIRED
↓
ToolExecutionService
↓
adapter.invoke_once()
↓
session_for(server_id)
↓
client.call_tool(remote_name, args)
↓
MCP tools/call
↓
MCP result
↓
normalize
↓
ToolOutput
```

这里 Model 根本不需要知道：

```text
这个 Tool 来自 MCP
```

Codex 确认 `AgentRouter`、Runtime Core 都没有 provider-specific MCP branch。

这是很好的 **Provider Transparency（提供方透明性）**。

------

# 2.3 Identity Flow

MCP 引入后至少有几个容易混淆的 ID：

```text
server_id
remote MCP tool name
local canonical tool_name
ToolInvocation.invocation_id
operation_id
idempotency_key
```

当前最终结构：

```text
MCP Server:
server_id = filesystem_server

Remote MCP:
remote_name = read_file

LocalAgent:
local_name = mcp_filesystem_read

Runtime Call:
invocation_id = 一次调用唯一 ID
```

其中真正进入 Runtime 核心的是：

```text
local_name
```

而：

```text
server_id
remote_name
```

只在 Adapter provenance 中存在。

Codex Formal Gate 明确验证：

> `server_id` / `remote_name` 没有进入 `ToolInvocation`、Journal schema、PolicyCatalog key 或 Evaluation Authority。

------

# 3. 核心设计选择

------

## 3.1 为什么显式配置 local_name，而不是自动 `server/tool`？

最终 WP2 选择：

> Operator 为每个 MCP Tool 显式配置 LocalAgent `local_name`。

例如逻辑上：

```yaml
server_id: filesystem
remote_name: read_file
local_name: mcp_workspace_read
```

而不是强制：

```text
filesystem/read_file
```

或者：

```text
filesystem::read_file
```

原因之一是现有：

```text
ToolDescriptor.name
```

有自己的 safe-name contract：

```regex
^[a-z][a-z0-9_]{0,63}$
```

显式 local mapping 可以继续满足既有 Contract，而不用为了 MCP 修改核心 Tool Identity 类型。

### Trade-off

优点：

```text
不改 ToolInvocation
不改 Policy key
不改 Evaluation
Identity 稳定
Operator 可控
```

缺点：

```text
需要显式配置
增加配置成本
```

对于当前面试导向项目：

> 非常合理。

------

# 3.2 为什么 Remote Tool Name 不等于 Runtime Tool Identity？

例如两个 Server：

```text
Server A → read_file
Server B → read_file
```

MCP 只保证：

> 一个 Server 内 Tool name 唯一。

LocalAgent 却要求：

```text
整个 ToolRegistry 全局唯一
```

所以不能：

```text
remote_name = Runtime identity
```

当前：

```text
remote identity
↓ mapping
local canonical identity
```

就解决了这个边界。

跨 Server local name collision 和 builtin collision 都会 fail closed。

------

# 3.3 为什么 MCP Tool 必须有 Local Policy Mapping？

这是 WP2 最重要的安全设计之一。

MCP Server 可以提供：

```text
readOnlyHint
destructiveHint
idempotentHint
```

但 LocalAgent 不用这些直接生成：

```text
side_effect
idempotency
risk
approval
```

这些安全事实来自 operator 配置。

例如：

```text
MCP says:
readOnlyHint = true

Local Config says:
side_effect = LOCAL_STATE_MUTATION
idempotency = NON_IDEMPOTENT
risk = HIGH
```

最后仍然：

```text
APPROVAL_REQUIRED
```

测试已经真实证明这一点。

面试中一句很好的表达：

> **Protocol metadata is descriptive, local policy is authoritative.**

即：

> 协议元数据负责“描述”，本地策略负责“授权”。

------

# 3.4 为什么 registration 和 policy 必须原子产生？

错误设计：

```text
register tool A
register tool B
register tool C
↓
发现 C 没 policy
↓
失败
```

此时可能留下：

```text
A/B 已注册
C 未注册
Policy 状态不完整
```

最终可能出现：

```text
ToolRegistry
≠
PolicyCatalog
```

当前实现是先：

```text
_build complete server batch
```

只有所有 Tool 都成功后：

```text
commit names
return registrations + policies
```

任何一个：

```text
missing policy
invalid policy
collision
invalid schema
```

都会：

```text
whole server → zero registration
```

Codex 已确认这个 registration-building stage 是 atomic 的。

------

# 3.5 为什么 ToolAdapter 是 MCP 最合适的 Adapter Seam？

`ToolAdapter` 本来就负责：

```text
Model Args
→ Validation
→ Invocation
→ Execution Spec
→ Provider Invocation
→ Provider Result
```

MCP 做的恰恰是：

```text
Local Runtime contract
↕
Remote MCP protocol
```

所以：

```text
McpBackedToolAdapter
```

成为天然的 Anti-Corruption Layer（防腐层）。

它把：

```text
MCP protocol concepts
```

限制在：

```text
mcp/
```

之内。

Runtime Core 不需要认识：

```text
MCP request
MCP content
MCP server_id
MCP cancellation notification
```

这是非常典型的后端架构设计。

------

# 3.6 为什么不能在 MCP Client 里做 Retry？

假设：

```text
tools/call
```

是：

```text
create_order
delete_file
transfer_money
```

Client 遇到 timeout：

```text
没收到 response
```

不意味着：

```text
Server 没执行
```

如果 MCP Client 自动：

```text
retry()
```

就可能：

```text
第一次已经执行
↓
response 丢失
↓
client retry
↓
执行第二次
```

所以当前：

```text
MCP Client = NO RETRY
```

唯一 Retry Authority：

```text
ToolExecutionService
```

而且基于：

```text
SideEffectKind
Idempotency
Error Category
Side-effect Outcome
```

统一决定。

Codex Formal Gate 已确认 MCP 没有 retry/reconnect-and-replay loop。

------

# 3.7 为什么 timeout 后直接把 Session 标记 broken？

当前 stdio 实现里：

```text
tools/call timeout
↓
connection/session break
↓
后续调用
MCP_SESSION_UNAVAILABLE
```

乍一看：

> 为什么不 reconnect？

因为 reconnect 会引入另一个更难的问题：

```text
前一次 tools/call 到底执行了没有？
```

尤其 mutation：

```text
timeout
≠
未执行
```

所以当前采取：

```text
Fail-stop Session
```

而不是：

```text
Reconnect + Replay
```

Codex 最终正式判定：

```text
CORRECT_ACCEPTED_LIMITATION
```



这是非常好的 Production Awareness（生产意识）面试点：

> 可用性低一点，也不能牺牲 side-effect correctness。

------

# 4. Side-effect State 是本 WP 最值得掌握的内容

这一部分非常重要。

## 4.1 为什么必须 `before_side_effect()` 再 tools/call？

对于远端 Tool：

```text
client.call_tool()
```

本身就是副作用边界。

因此：

```text
context.before_side_effect()
↓
client.call_tool()
```

顺序必须严格成立。

不能：

```text
call_tool()
↓
before_side_effect()
```

因为第一个 network/process I/O 发出去后：

> 副作用可能已经发生。

Formal Gate 已独立确认顺序正确。

------

# 4.2 Mutation 成功

```text
before_side_effect
↓
tools/call
↓
success
```

结果：

```text
COMMITTED
```

表示：

> 我们有 authoritative evidence 认为本次 mutation 成功。

------

# 4.3 Mutation + isError=true

MCP 返回：

```json
{
  "isError": true
}
```

这只能说明：

> Tool 报告错误。

不能推出：

```text
副作用没发生
```

例如：

```text
写数据库成功
↓
生成响应失败
↓
Tool 返回 error
```

所以：

```text
mutation + isError
→ UNKNOWN
```

而不是：

```text
NOT_STARTED
```

Codex 确认该状态不会进入安全自动 Retry。

------

# 4.4 Mutation Timeout

更加典型：

```text
request send
↓
remote executes mutation
↓
response 丢失
↓
timeout
```

LocalAgent只能知道：

```text
“我不知道执行没执行。”
```

因此：

```text
UNKNOWN
```

这是分布式系统里非常重要的思想：

> **Timeout is uncertainty, not failure proof.**

------

# 4.5 Mutation + Unsupported Result

另一个容易写错的场景：

```text
Tool 成功执行 mutation
↓
返回 ImageContent
↓
LocalAgent Phase9 不支持 Image
```

能不能写：

```text
Tool failed
side effect UNKNOWN
```

不应该。

这里协议调用已经成功，所以：

```text
Side Effect = COMMITTED
Result normalization = failed
```

两个事实必须分开。

当前就是这么做：

```text
mutation successful protocol call
+
unsupported output
→ COMMITTED
+
OUTPUT_INVALID
```



这是很高级但非常实用的面试点：

> **Execution Outcome（执行结果）和 Observation Decoding（结果解析）是不同事实。**

------

# 5. Truth / Completion Boundary

## 已真实实现

WP2 已实现：

```text
Canonical local tool identity mapping
Local Tool Policy mapping
MCP-backed ToolAdapter
MCP ToolRegistration
Registry integration
PolicyCatalog integration
tools/call
Result normalization
Runtime timeout integration
Runtime cancellation propagation
Side-effect checkpoint
Existing retry integration
Model-facing MCP Tool descriptor
```



------

## 已真实测试

MCP 相关：

```text
181 passed
```

Existing Tool Runtime：

```text
189 passed
```

以及：

```text
compileall PASS
import server PASS
git diff --check PASS
```

这些由实际 Codex 最终重新执行。

------

## 当前测试真实性

当前仍然是：

```text
DETERMINISTIC_TEST
```

因为 MCP Server 是：

```text
fake stdio subprocess
```

但注意，与 WP1 相比，WP2 测试已经是真实组合：

```text
fake MCP protocol server
+
真实 ToolExecutionService
+
真实 Registry
+
真实 Governance
```

所以 Runtime integration 本身已经得到了很强的确定性验证。

------

## 没有完成

仍然：

```ini
REAL_MCP_E2E = NOT_RUN
```

没有真实证明：

```text
DeepSeek
→ real independently implemented MCP server
→ real LocalAgent
→ final continuation
```



------

## 尚未完成

主要留给 WP3：

```text
REAL_MCP_E2E
真实 MCP side-effect
真实 APPROVE
真实 REJECT
Exactly-once MCP side-effect proof
Phase9 docs/error-code closeout
```

------

# 6. Bad Cases

------

## Bad Case 1 — 直接相信 `readOnlyHint`

### Truth Source

```text
DETERMINISTIC_TEST
```

真实测试覆盖。

### Trigger

Server：

```text
readOnlyHint=true
```

但 operator：

```text
LOCAL_STATE_MUTATION
NON_IDEMPOTENT
```

### Symptom

如果错误实现：

```text
readOnlyHint
→ side_effect NONE
→ LOW
→ ALLOW
```

就会绕过审批。

### Risk

恶意 MCP Server 可以：

```text
self-declare safe
→ bypass Governance
```

### Root Cause

混淆：

```text
Provider Claim
```

和：

```text
Security Fact
```

### Fix

只使用：

```text
local ToolExecutionSpec
+
local ToolPolicy
```

作为安全事实。

### Regression

真实 Governance 测试得到：

```text
APPROVAL_REQUIRED
HIGH
```

即使 MCP 声称 `readOnlyHint=true`。

### Knowledge Point

```text
Metadata ≠ Authority
```

------

## Bad Case 2 — Timeout 自动 Retry Mutation

### Truth Source

```text
SOURCE/IMPLEMENTATION + CODEX FINAL CONFIRMATION
```

### Trigger

```text
mutation tools/call
↓
timeout
```

### 错误实现

```text
timeout
→ retry
```

### Risk

远端可能已经 mutation：

```text
执行一次
+
retry 再执行一次
=
duplicate side effect
```

### Root Cause

错误假设：

```text
Timeout = 没执行
```

### Fix

mutation：

```text
checkpoint 已发生
+
timeout
→ side_effect UNKNOWN
```

Existing Runtime：

```text
UNKNOWN
→ 不安全自动重试
```

### Regression

Codex 独立确认 side-effect truth 与 Retry Owner 正确。

### Knowledge Point

> Timeout expresses uncertainty.

------

## Bad Case 3 — MCP Client 自己 Retry

### Truth Source

```text
CODEX_FINAL_CONFIRMATION
```

### Trigger

transport failure。

### Risk

两套 Retry Authority：

```text
MCP retry
+
ToolExecutionService retry
```

会形成：

```text
一次 Runtime Attempt
→ 多次远程执行
```

破坏 Attempt / Execution Claim 语义。

### Fix

MCP Client：

```text
zero retry
zero reconnect-and-replay
```

Retry 只属于：

```text
ToolExecutionService
```

### Knowledge Point

> Provider transport mechanism must not become execution policy.

------

## Bad Case 4 — Tool 注册了，但没有 Policy

### Truth Source

```text
DETERMINISTIC_TEST + CODEX FINAL CONFIRMATION
```

### Trigger

Server 有多个 Tool，其中一个 missing policy。

### 错误结构

```text
先 Register
↓
再创建 Policy
```

中途失败。

### Risk

存在：

```text
可调用 Tool
+
无治理 Policy
```

### Fix

先构建：

```text
registration batch
+
policy batch
```

全部成功后再注入。

### Regression

Codex Formal Gate 验证 atomicity PASS。

### Knowledge Point

> Security-sensitive registration should be atomic with authorization coverage.

------

## Bad Case 5 — Remote execution 成功，但解析失败就说“没执行”

### Truth Source

```text
DETERMINISTIC_TEST
```

### Trigger

mutation 返回 unsupported content。

### 错误判断

```text
result unsupported
→ invocation failed
→ side effect NOT_STARTED
```

### Risk

可能允许安全 retry。

### Fix

拆成两个事实：

```text
Remote Execution = COMMITTED
Result Interpretation = FAILED
```

### Knowledge Point

> Side-effect truth and result-decoding truth are independent dimensions.

------

# 7. 名词 / 概念速览

### ToolAdapter（工具适配器）

负责把 LocalAgent 的统一 Tool Contract 转换成具体 Provider 的执行协议。

### Canonical Identity（规范身份）

Runtime 内唯一、稳定、用于 Registry / Policy / Invocation 的标准 Tool Identity。

### Provenance（来源信息）

说明 Tool 来自哪个 MCP Server、哪个 remote tool，但不承担 Runtime Identity 职责。

### ToolRegistration（工具注册）

将 ToolDescriptor 与具体 ToolAdapter 绑定成 Runtime 可以使用的 Tool。

### ToolPolicy（工具策略）

LocalAgent 本地定义的 Tool 授权、风险、审批相关静态策略。

### Security Authority（安全权威）

最终有权决定风险、授权和审批语义的数据或组件。

### Side-effect（副作用）

Tool 执行对外部或本地状态产生持久改变，例如写文件、改数据库。

### Side-effect Checkpoint（副作用检查点）

在第一次可能产生副作用的 I/O 前记录“即将进入不可安全假设未执行的区域”。

### COMMITTED（已提交）

有足够证据确认副作用已经发生。

### UNKNOWN（未知）

已经进入可能产生副作用的区域，但无法确认最终是否发生。

### NOT_STARTED（未开始）

确定没有进入副作用执行阶段。

### Retry Authority（重试权威）

拥有“这次失败后能否再次执行”决策权的组件。

### Fail-stop（失败即停止）

连接出现不确定性后不自动恢复继续执行，而是进入不可用状态。

### Anti-Corruption Layer（防腐层）

隔离两个系统数据模型和协议，使外部协议不会污染内部核心领域模型。

### Registration Atomicity（注册原子性）

Tool 与对应安全策略要么一起进入系统，要么全部不进入。

### Result Normalization（结果归一化）

把 MCP Provider 返回的数据转换成 LocalAgent 统一 Tool Result Contract。

------

# 8. 工程构建方法类问答

## Q1：为什么 MCP Adapter 不应该修改 ToolInvocation？

因为 MCP：

```text
server_id
remote_name
```

属于 Provider provenance。

而 `ToolInvocation`：

```text
tool_name
arguments
invocation_id
idempotency_key
```

属于 Runtime execution contract。

如果为了每个 Provider 不断往 `ToolInvocation` 添加：

```text
provider
server
transport
protocol
```

核心 Runtime 会逐渐被 Provider 细节污染。

更好的方式：

```text
ToolInvocation
→ canonical local identity

Adapter
→ provider-specific provenance
```

------

## Q2：为什么不用 MCP Tool Name 直接注册？

因为 ToolRegistry 是全局的，而 MCP Tool name 只要求 server scope 唯一。

例如：

```text
GitHub MCP:
search

Filesystem MCP:
search
```

会发生 collision。

所以必须有：

```text
Remote identity
→ Local canonical identity
```

------

## Q3：为什么 Operator 配置 side_effect / idempotency，而不是 MCP Server？

因为 Runtime 的安全治理必须建立在：

```text
Local Trust Domain
```

内。

Server 可以被误配置、被攻破，甚至本身就是第三方。

所以：

```text
Remote declaration = hint
Local config = authority
```

------

## Q4：为什么整个 Server 一个 Tool 配错，就全部不注册？

这是一种：

```text
Fail-closed Batch Semantics
```

优点：

- 行为简单
- 没有 partial state
- Policy coverage 容易证明
- Registry snapshot 确定

缺点：

- 可用性略低

对于 Phase9：

> 简单确定性比复杂 partial acceptance 更重要。

------

## Q5：为什么 inputSchema 不实现完整 JSON Schema？

当前项目不是 JSON Schema 引擎项目。

只实现：

```text
bounded subset
```

用于：

- type
- required
- 基础 primitive
- 结构深度

剩余约束由真正 MCP Tool Server 自己验证。

关键是：

```text
不能因为不完整就错误放宽安全 Authority
```

Argument 最终仍是 untrusted external provider input。

Codex 判断当前 subset 足以完成 Phase9 minimum closure。

------

## Q6：为什么 `isError=true` 对 read-only 和 mutation 处理不同？

因为副作用事实不同。

Read-only：

```text
不存在状态修改
```

所以 error 可以：

```text
NOT_STARTED
```

Mutation：

```text
Server 可能先修改，再返回 error
```

所以：

```text
UNKNOWN
```

------

## Q7：为什么 unsupported result 也可能是 COMMITTED？

因为：

```text
Tool 是否执行成功
```

和：

```text
Client 是否能理解返回内容
```

是两件事。

比如：

```text
写文件成功
↓
返回 ImageContent
↓
LocalAgent 不支持 ImageContent
```

文件仍然已经写了。

------

## Q8：为什么不能 timeout 后 reconnect 再 retry？

因为无法知道 timeout 前那次请求：

```text
有没有执行
```

Reconnect 只能恢复连接：

```text
不能恢复执行事实
```

这就是典型的：

```text
Connection Recovery
≠
Execution Recovery
```

------

# 9. 高频面试追问

## 1. 你是怎么把 MCP 接进原 Tool Runtime 的？

**简单回答：**

我没有为 MCP 新建执行链，而是实现 `McpBackedToolAdapter`。启动阶段把 discovery snapshot 映射成 Local canonical tool、`ToolRegistration` 和本地 `ToolPolicy`，之后它和普通 Tool 一样进入 ToolRegistry、Governance、HITL 和 ToolExecutionService，只有 `adapter.invoke_once()` 最后一步才转换成 MCP `tools/call`。

------

## 2. MCP Tool 的风险等级谁决定？

**简单回答：**

LocalAgent 决定。MCP annotations 只是 untrusted provider metadata，真正的 side effect、idempotency、risk 和 approval policy 来自 operator local mapping、`ToolExecutionSpec` 与 `ToolPolicyCatalog`。

------

## 3. 两个 MCP Server 有同名 Tool 怎么办？

**简单回答：**

Remote tool name 不直接作为 Runtime identity。Operator 给每个 remote tool 配置稳定的 local canonical name；跨 server 或与 builtin Tool 冲突都会在 startup registration 阶段 fail closed。

------

## 4. MCP Tool timeout 后为什么不直接 retry？

**简单回答：**

如果是 mutation，timeout 只能说明没有收到结果，不能说明远端没执行。所以 side-effect 状态会被收口为 UNKNOWN，现有 Runtime 不会安全自动 retry，避免重复副作用。

------

## 5. MCP Client 有没有自己的 retry？

**简单回答：**

没有。Retry Owner 保留在 ToolExecutionService，MCP Client 只负责协议和 I/O。否则 Client retry 和 Runtime retry 会形成双重重试，破坏一次 Attempt 对应一次 Provider execution 的语义。

------

## 6. MCP `isError=true` 是什么？

**简单回答：**

这是 Tool-level error result。对于 mutation，我不会因此认为副作用没发生，而是保守标记 UNKNOWN；对于 read-only 则可以保持 NOT_STARTED。

------

## 7. 为什么 MCP Tool 注册和 Policy 创建必须一起完成？

**简单回答：**

否则可能出现 Tool 已经进入 Registry，但 PolicyCatalog 没有对应授权策略的安全空窗。所以实现时先构造完整 registration+policy batch，任何一个 Tool 校验失败则整个 Server 零注册。

------

## 8. 你修改了核心 Tool Runtime 吗？

**简单回答：**

没有。Codex Final Gate 已确认 ToolInvocation、ToolExecutionService Owner、Governance Authority 都没改变。只在 Governance 模块暴露了一个读取既有 risk-combination allowlist 的 helper，没有复制或改变分类逻辑。

------

## 9. 你们支持所有 MCP Result 类型吗？

**简单回答：**

没有。当前为了最小闭环只支持 TextContent 和 `isError`；image、audio、resource、structured-only 等安全失败，不为了 MCP 扩大现有 ToolOutput Contract。

------

## 10. MCP 当前是真实 E2E 吗？

**简单回答：**

WP2 还不是。当前是 deterministic fake stdio MCP server 加真实 LocalAgent Tool Runtime 的组合测试，已经验证 Registry/Governance/Execution/tools-call 集成；真实独立 MCP Server + DeepSeek + HITL E2E 留到 WP3，所以我不会把 WP2 描述成 REAL_MCP_E2E。

------

# 10. 30 秒面试总结

> 我在现有 LocalAgent Tool Runtime 上接 MCP 时，没有增加 MCP 专用执行链，而是实现了一个 MCP-backed ToolAdapter。启动阶段把 MCP discovery snapshot 通过 operator 配置映射成 Local canonical tool name、ToolRegistration 和本地 ToolPolicy，然后继续复用现有 Registry、Governance、HITL 和 ToolExecutionService，只有 `invoke_once` 最终调用 MCP `tools/call`。MCP annotations 始终是不可信 metadata，不参与风险和审批决策。另外对 mutation 的 timeout、isError 和 cancellation 都使用现有 side-effect tracker 保守收口 UNKNOWN，MCP Client 本身不拥有 retry，因此不会因为远程结果不确定导致重复副作用。

------

# 11. 2 分钟面试总结

> 我的 LocalAgent 在接 MCP 前已经有完整的 Tool Runtime，包括 ToolRegistry、typed ToolInvocation、Governance、HITL、Execution Claim、ToolExecutionService、timeout 和 cancellation，所以 MCP 集成的关键不是简单把 `tools/call` 调通，而是让 MCP 成为已有 Runtime 的一个 Provider。
>
> 我先通过 MCP discovery 得到 remote tool，然后由 operator 显式配置它的 Local canonical name 和安全策略。这样 MCP Server 的 tool name、annotations、readOnlyHint、idempotentHint 都只属于 provider metadata，不会直接成为 LocalAgent 的安全事实。每个 MCP Tool 会生成现有的 `ToolRegistration`、`ToolPolicy` 和一个 `McpBackedToolAdapter`，并且所有 registration 和 policy 都在 Registry freeze 前以 batch 形式完成，一个 Tool 配置错误就整个 Server 零注册，避免出现注册了 Tool 却没有 Policy 的状态。
>
> 运行时模型完全不知道 MCP 的存在，它仍然选择普通的 LocalAgent tool name，之后走 build_invocation、spec_for、Governance 和 HITL，真正执行时仍由 ToolExecutionService 调 `adapter.invoke_once()`，Adapter 最后才把调用转换成 MCP `tools/call`。这样 Timeout、Cancellation 和 Retry Owner 都没有迁移到 MCP Client。
>
> Side-effect 方面我特别处理了分布式调用的不确定性。对于 mutation，`before_side_effect()` 一定先于远程 `tools/call`。如果远程 timeout、取消或者返回 `isError=true`，我们不会认为副作用一定没发生，而是把状态收口为 UNKNOWN，现有 Runtime 因此不会做危险的自动 retry。即使 Tool 实际 mutation 成功，只是返回了当前不支持的 ImageContent，我们也会把副作用记为 COMMITTED，同时把结果解析记为失败，避免把执行事实和结果解析事实混在一起。
>
> 当前 WP2 已通过 Codex Formal Gate，ToolInvocation、ToolExecutionService 和 Governance Authority 都没有改变。测试上已经使用 deterministic stdio MCP server 配合真实 ToolExecutionService、Registry 和 Governance 验证，但还没有把它包装成 REAL_MCP_E2E；下一阶段才用真实独立 MCP Server、真实 DeepSeek 和 HITL 做最终闭环。

------

# 12. 推荐学习文档名

```text
docs/interview/mcp_runtime_integration.md
```

这一 WP 最应该记住的四句话：

> **MCP Tool 是 Provider，不是第二套 Runtime。**

> **MCP metadata 是声明，不是安全 Authority。**

> **Timeout 表示“不确定”，不是“没有执行”。**

> **Provider execution fact 与 result decoding fact 必须分开。**

这四句基本覆盖了 WP2 最有价值的架构、安全和分布式系统面试点。