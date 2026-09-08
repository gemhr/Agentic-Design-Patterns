当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase9-WP1 学习 / 面试总结

## MCP Client + Discovery Boundary Foundation

------

## 1. 本 WP 解决了什么问题

### 原问题

WP0 已经决定 MCP（Model Context Protocol，模型上下文协议）不能成为第二套 Tool Runtime，但当时 LocalAgent 实际上完全没有可执行 MCP 能力。

WP1 要解决的是 MCP 接入的最外层基础问题：

```text
LocalAgent
   ↓
如何连接一个 MCP Server？
   ↓
如何完成 initialize？
   ↓
如何发现它有哪些 Tools？
   ↓
谁负责 Client / Session 生命周期？
   ↓
怎样把 Server 返回的数据安全带回 LocalAgent？
```

而**不是**直接解决：

```text
如何执行 MCP Tool
```

这两个问题要严格拆开。

### 为什么值得解决

如果直接从 `tools/call` 开始，很容易变成：

```text
Model
  ↓
MCP Client
  ↓
MCP Server
```

这样实际上绕开了 LocalAgent 已经完成的：

```text
ToolRegistry
Validation
Governance
HITL
Execution Claim
ToolExecutionService
Timeout / Cancellation
Journal
```

所以 WP1 先建立一个**纯 Provider Boundary（外部提供方边界）**。

### 本 WP 的真实边界

最终真实实现的是：

```text
operator MCP config
        ↓
StdioMcpClient
        ↓
initialize
        ↓
capability check
        ↓
notifications/initialized
        ↓
tools/list
        ↓
McpToolDescriptor
        ↓
McpDiscoverySnapshot
```

到这里停止。

没有产生 `ToolRegistration`，也没有执行 `tools/call`。

------

# 2. 真实架构 / 数据流 / 状态流

## 2.1 Startup 数据流

当前真正的数据流：

```text
LOCAL_AGENT_MCP_CONFIG_PATH
        ↓
Settings.load()
        ↓
load_mcp_server_configs()
        ↓
server.py::lifespan()
        ↓
RuntimeInitializationStack
        ↓
McpIntegrationComponent.start()
        ↓
StdioMcpClient
        ↓
spawn MCP Server subprocess
        ↓
initialize
        ↓
capability negotiation
        ↓
notifications/initialized
        ↓
tools/list
        ↓
McpToolDescriptor[]
        ↓
McpDiscoverySnapshot
```



这里一个很重要的词是：

> **Discovery Snapshot（发现快照）**

它的意思不是“动态 MCP Marketplace”。

而是：

> 应用启动时看一遍 MCP Server 当前有哪些 Tool，然后得到一份不可随意变化的发现结果。

------

## 2.2 Lifecycle（生命周期）

Client / Session Owner 被实现成：

```text
Application Scope
```

也就是：

```text
LocalAgent startup
        ↓
创建 MCP Integration Component
        ↓
创建每个 server session
        ↓
整个应用生命周期复用
        ↓
LocalAgent shutdown
        ↓
统一关闭 session / subprocess
```

不是：

```text
每个请求创建 MCP Client
```

也不是：

```text
每次 tools/call 启动一个 MCP Server
```

Codex Review 已验证，MCP session 没有进入：

```text
RunContext
AgentState
Snapshot
Recovery
```



------

## 2.3 MCP Server 状态

WP1 当前可以理解为三类：

```text
DISABLED
AVAILABLE
DISCOVERY_FAILED
```

其中单个 MCP Server discovery 失败：

```text
Server A → DISCOVERY_FAILED
Server B → AVAILABLE
LocalAgent → 仍然启动
```

但 Server A：

```text
不会留下可用 Session
不会产生 Descriptor
不会注册残缺 Tool
不会使用旧 Snapshot
```

Codex 最终接受了这种 **Degraded Startup（降级启动）** 策略。

------

# 3. 核心设计选择

## 3.1 为什么用 stdio，而不是先做 HTTP

最终冻结：

```ini
MCP_TRANSPORT = STDIO_FIRST
```

WP1 只实现 stdio。

结构可以理解为：

```text
LocalAgent Process
        ↓ spawn
MCP Server Process
        ↕
stdin / stdout
```

### 好处

第一，LocalAgent 是当前 owner：

```text
我启动你
我关闭你
我知道你什么时候退出
```

第二，适合：

```text
本机开发
面试 Demo
单机 Agent
```

第三，不需要一开始引入：

```text
HTTP Auth
TLS
Endpoint Trust
Session Header
Reconnect
Remote Deployment
```

所以本质是：

> 不是 stdio 比 HTTP 更高级，而是它是当前 Phase9 最小闭环的合理 Trade-off（权衡）。

------

# 3.2 为什么 Discovery 只发生在 Startup

因为 LocalAgent 当前：

```text
ToolRegistry
PolicyCatalog
```

都有：

```text
register
↓
freeze
↓
read-only
```

这样的生命周期。

所以：

```text
startup discovery
↓
后续 WP 注册 Tool
↓
Registry freeze
```

非常自然。

反过来，如果实现：

```text
tools/listChanged
↓
runtime refresh
↓
动态新增 Tool
```

马上就会引入：

```text
Registry 如何重新 freeze？
Policy 如何同步？
Model 已看到的 tool descriptors 怎么更新？
正在执行的 Run 怎么办？
Evaluation 怎么保证 identity 稳定？
```

这已经不是 MCP Adapter 问题，而是 Runtime Lifecycle redesign（运行时生命周期重设计）。

所以 WP1 明确没有：

```text
refresh
listChanged
hot reload
runtime registration
```



------

# 3.3 为什么 MCP metadata 必须是不可信的

目前：

```text
McpToolDescriptor
```

里会保存：

```text
server_id
remote_name
description
input_schema
annotations
```

但没有：

```text
risk
permission
approval
side_effect
idempotency
```



原因非常关键。

MCP Server 可能告诉你：

```text
readOnlyHint = true
```

但 LocalAgent 不能因此直接认为：

```text
这是只读安全工具
```

因为这个信息来自：

> 外部 Server 自己。

所以当前边界：

```text
MCP metadata
=
Provider-declared Metadata
=
Untrusted External Input
```

以后 WP2 真正决定：

```text
side_effect
idempotency
risk
approval
```

仍然由 LocalAgent 本地 Runtime 负责。

这是非常值得在面试中讲的安全设计。

------

# 3.4 为什么不用官方 MCP metadata 直接做 Governance

可以这样回答：

> 协议解决互操作性，不等于解决信任问题。

MCP Server 能说：

```text
我是 read only
```

但协议只是让它可以表达这个声明。

它并不能保证：

```text
声明一定是真实的
```

因此：

```text
Protocol Metadata
≠
Security Authority
```

------

# 3.5 为什么 Client 是 Application Scope

另外两个候选是：

### Run Scope

```text
每个 Agent Run 创建 Client
```

问题：

```text
重复 initialize
重复 tools/list
额外 subprocess
难以处理 shutdown
```

### Tool-call Scope

```text
每次 Tool 调用创建 Client
```

更差：

```text
spawn
initialize
call
destroy
```

一次 Tool 调用就要重复完整协议初始化。

因此 Application Scope 更符合当前：

```text
startup discovery
+
frozen Registry
```

设计。

------

# 4. Truth / Completion Boundary

这一部分面试时尤其不能说错。

## 已真实实现

已经实现：

```text
stdio MCP Client
subprocess lifecycle
initialize
protocol version check
capability negotiation
notifications/initialized
tools/list pagination
MCP configuration
MCP discovery snapshot
application-scope session lifecycle
MCP boundary error taxonomy
bounded metadata validation
bounded shutdown
```



------

## 已真实测试

真实运行了本地确定性 fake stdio MCP Server subprocess。

Codex Review 后定向测试：

```text
139 passed
compileall PASS
import server PASS
git diff --check PASS
```



这是：

```text
DETERMINISTIC_TEST
```

------

## 还没有真实证明

目前**没有**：

```text
REAL_MCP_E2E
```

因为使用的是：

```text
测试内嵌 fake MCP server
```

而不是一个真实独立 MCP 实现。

------

## 尚未实现

```text
tools/call
MCP-backed ToolAdapter
ToolRegistration
canonical local tool name mapping
local Policy mapping
MCP Governance execution
MCP HITL
REAL_MCP_E2E
```

这些属于后续 WP。

------

## Accepted Limitations

当前三个：

```text
只支持 MCP 2025-06-18 protocol version

只支持 startup snapshot

只支持 stdio discovery
```

不支持：

```text
listChanged
refresh
runtime registration
Streamable HTTP
tools/call
```



------

# 5. Bad Cases

WP1 有两个非常适合面试的真实 Bad Case。

------

## Bad Case 1 — kill 之后仍然无限等待

### Truth Source

```text
CODEX_REVIEW_DISCOVERY
```

真实 Code Review 发现。

### Trigger

MCP Server 卡死：

```text
stdin close
失败
↓
terminate
失败
↓
kill
↓
process.wait()
```

原实现最后的 `process.wait()` 没有 timeout。

### Symptom

即使已经 `kill()`：

```text
LocalAgent shutdown
```

仍可能永久阻塞。

### Risk

这意味着：

> 一个不可信 MCP 子进程可以拖死整个 LocalAgent shutdown。

对于 Agent Runtime，这是典型的：

```text
Lifecycle Availability Bug
```

### Root Cause

把：

```text
kill()
```

错误理解成：

```text
process 一定已经完成退出
```

实际上：

```text
发出 kill
≠
已经确认 process terminated
```

### Fix

改为：

```text
close 总预算
↓
stdin close wait
↓
terminate wait
↓
kill wait
```

三个阶段都 bounded。

如果最终仍然没有确认退出：

```text
return False
```

而不是无限等。



### Regression

Codex fix-forward 后：

```text
139 targeted tests passed
```



### Knowledge Point

> **Kill is an action, not a completion fact.**

也就是：

> 发出终止信号和确认生命周期结束是两件事。

这个思想和你之前 Runtime 的：

```text
Execution Claim
Terminal State
Cancellation
```

其实是一脉相承的。

------

# Bad Case 2 — JSON 有大小限制，但仍然可以用深度打爆解析

### Truth Source

```text
CODEX_REVIEW_DISCOVERY
```

### Trigger

恶意 Server 返回非常深的：

```json
{"a":{"a":{"a":{"a": ... }}}}
```

或者：

```text
NaN
Infinity
```

等非标准值。

### Symptom

原实现虽然有：

```text
schema size limit
metadata size limit
```

但：

> 大小有限 ≠ 结构复杂度有限。

深层数据仍可能：

```text
递归爆栈
parser exception escape
```

### Risk

MCP Server 属于：

```text
untrusted external process
```

这意味着 discovery 本身就是攻击面。

### Root Cause

只有：

```text
Byte Size Bound
```

没有：

```text
Structural Complexity Bound
```

### Fix

增加：

```text
max depth = 32
allow_nan = False
```

并把递归/解析错误统一转换为 MCP boundary protocol error。



### Regression

定向 MCP tests PASS。

### Knowledge Point

> **Resource Bounding（资源限制）不能只限制字节数，还要限制结构复杂度。**

这是后端和 Agent 安全面试里都很好的点。

------

# 6. 名词 / 概念速览

### MCP（Model Context Protocol，模型上下文协议）

一种让模型应用与外部 Tool / Resource / Prompt Provider 使用标准协议交互的协议。

### Transport（传输层）

MCP Client 与 Server 之间实际传输协议消息的机制，例如 stdio 或 Streamable HTTP。

### stdio（标准输入输出）

Client 通过子进程 stdin/stdout 与 MCP Server 交换 JSON-RPC 消息。

### JSON-RPC

一种基于 JSON 的远程调用协议，使用 request id 区分请求和响应。

### Capability Negotiation（能力协商）

初始化时 Client 和 Server 声明自己支持的协议能力。

### Discovery（发现）

Client 查询 Server 当前暴露哪些能力；WP1 主要是 `tools/list`。

### Discovery Snapshot（发现快照）

启动时获取一次 Tool 列表并固定下来，不持续动态刷新。

### Application Scope（应用级作用域）

对象生命周期覆盖整个应用启动到关闭，而不是某个请求或某次 Tool 调用。

### Provider Metadata（提供方元数据）

由 MCP Server 提供的工具描述、Schema、Annotation 等信息。

### Untrusted External Data（不可信外部数据）

来自系统信任边界之外的数据，使用前必须校验、限制，不能直接作为安全事实。

### Fail Closed（失败关闭）

无法确认安全或正确时拒绝继续，而不是猜测或默认放行。

### Degraded Startup（降级启动）

某个非核心外部组件失败时，主应用仍可启动，但该组件能力不可用。

### Bounded Shutdown（有界关闭）

关闭外部资源最多等待有限时间，防止 shutdown 无限卡死。

### Provenance（来源信息）

用于说明某项数据或 Tool 来自哪个 Server / Provider，但本身不等于 Runtime identity。

### Protocol Version（协议版本）

Client 与 Server 用于确认双方遵循哪一版 MCP 语义的版本号。

------

# 7. 工程构建方法类问答

## Q1：为什么 MCP Client 不直接放进 ToolExecutionService？

因为：

```text
ToolExecutionService
```

当前职责是：

> 执行一个已经解析好的 `ToolAdapter`。

如果它再负责：

```text
MCP server discovery
MCP session management
provider dispatch
```

就会变成：

```text
Execution Owner
+
Provider Registry
+
Transport Owner
```

职责膨胀。

所以正确方式是：

```text
ToolExecutionService
↓
未来 MCP-backed ToolAdapter
↓
MCP Client
```

不是：

```text
ToolExecutionService
↓
if mcp ...
```

------

# Q2：为什么 Tool Discovery 和 Tool Execution 要分开？

Discovery 回答：

> 有什么工具？

Execution 回答：

> 这一次调用怎么执行？

二者生命周期不同：

```text
Discovery → application startup

Execution → individual invocation
```

如果混在一起：

```text
每次 execute 重新 tools/list
```

会导致：

- Tool identity 不稳定
- Policy 难冻结
- 模型看到的 descriptor 变化
- 额外协议开销

------

# Q3：为什么 discovery failure 可以降级，而 config invalid 要 fatal？

因为两者代表不同问题。

### Invalid Config

表示：

```text
operator 配置本身错误
```

例如：

```text
格式非法
未知字段
command 非法
```

这是：

```text
Configuration Error
```

应该：

```text
fail fast
```

### Server unavailable

表示：

```text
外部依赖暂时不可用
```

而 MCP 当前：

```text
default disabled
optional integration
```

所以可以：

```text
LocalAgent startup success
MCP server = unavailable
```

但不能：

```text
继续注册残缺 Tool
```

Codex Review 最终接受了这个设计。

------

# Q4：为什么限制 tools/list 最多多少 Tool？

因为 MCP Server 是外部输入。

如果无限接受：

```text
1,000,000 tools
```

可能导致：

```text
startup memory explosion
huge model tool schema
DoS
```

当前已经有：

```text
servers ≤ 16
tools/server ≤ 128
pages ≤ 16
JSON line ≤ 1 MiB
description ≤ 2 KiB
schema ≤ 32 KiB
metadata ≤ 4 KiB
depth ≤ 32
```



------

# Q5：为什么 environment 不能直接完整继承父进程？

因为父 LocalAgent 进程可能包含：

```text
LLM API Key
Database credentials
internal token
```

如果：

```python
env=os.environ
```

直接传给任意 MCP Server，相当于：

> 把 LocalAgent 的 Secret 信任域扩展到了所有 MCP Server。

当前实现是：

```text
固定 Windows allowlist
+
operator 显式配置 environment
```



这是非常好的安全面试点。

------

# 8. 高频面试追问

## 1. 你项目里的 MCP 做到什么程度？

**简单回答：**

目前已经完成 stdio MCP Client、initialize、capability negotiation、startup `tools/list` discovery、application-scope session lifecycle 和配置安全边界；Tool execution、MCP-backed ToolAdapter、Governance/HITL 接入在后续 WP 完成。目前 discovery 测试是 deterministic fake server，不会冒充 REAL_MCP_E2E。

------

## 2. 为什么选择 stdio？

**简单回答：**

当前 LocalAgent 是单机开发和面试 Demo，stdio 可以由 LocalAgent 直接管理 MCP Server 子进程生命周期，不需要先引入 HTTP Auth、TLS 和 session/reconnect 复杂度，能最快完成标准 MCP 闭环。Streamable HTTP 被明确 defer，而不是否定。

------

## 3. MCP Server 的 `readOnlyHint` 可以直接信吗？

**简单回答：**

不能。它是 Provider-declared Metadata，不是 LocalAgent Runtime Security Fact。真正的 side-effect、risk、idempotency 和 approval 仍由本地 `ToolAdapter.spec_for()`、`ToolPolicyCatalog` 和 `ToolGovernanceService` 决定。

------

## 4. 为什么不用每次调用时 `tools/list`？

**简单回答：**

当前 ToolRegistry 和 PolicyCatalog 在 startup 后都会 freeze。如果 runtime 动态 discovery，就需要解决 Registry 更新、Policy reconciliation、model descriptor 一致性和正在执行 Run 的一致性问题，超出了 Phase9 的必要范围，所以当前使用 startup snapshot。

------

## 5. MCP Server 挂了 LocalAgent 要不要一起挂？

**简单回答：**

当前 MCP 是 optional integration。非法配置会让 startup fatal；但单个 Server connection/discovery failure 会降级为 `DISCOVERY_FAILED`，LocalAgent 继续运行，同时该 Server 不注册任何 Tool。这既保留可用性，也不会降级安全边界。

------

## 6. 为什么 Client 要 application scope？

**简单回答：**

因为 initialize 和 discovery 本身就是 startup 行为，并且 Registry 是 startup snapshot。Application-scope session 可以复用连接、统一 shutdown，也避免每次 Run 或 Tool call 重复 spawn 和 initialize。

------

## 7. MCP discovery 有哪些安全风险？

**简单回答：**

主要包括恶意 schema、超大 tool list、无限 pagination、深层 JSON、NaN/非法 JSON、环境变量泄漏、恶意 subprocess 卡死以及 metadata spoofing。因此我们对数量、大小、深度、分页和 shutdown 全部做 bounded processing，并将 metadata 保持为 untrusted。

------

## 8. 为什么有 size limit 还需要 depth limit？

**简单回答：**

因为几 KB 的 JSON 也可以构造非常深的嵌套结构，引发递归栈或解析复杂度问题。所以资源限制不仅要限制字节，还要限制结构复杂度。

------

# 9. 30 秒面试总结

> 我在 LocalAgent 里接 MCP 时没有直接做第二套 Tool Runtime，而是先实现了一个独立的 MCP Provider Boundary。WP1 完成了 stdio Client、initialize、capability negotiation、startup `tools/list` discovery 和 application-scope session lifecycle。MCP Server 返回的 Schema 和 annotations 全部按 untrusted provider metadata 处理，不直接成为风险、幂等性或审批事实。Discovery 使用 startup snapshot，与现有冻结 ToolRegistry/PolicyCatalog 生命周期保持一致。同时对 Server 数量、Tool 数量、JSON 大小和结构深度都做了限制，并解决了 MCP 子进程 shutdown 无界等待的问题。

------

# 10. 2 分钟面试总结

> 我项目原来已经有比较完整的 Tool Runtime，包括 ToolRegistry、typed ToolInvocation、Governance、HITL、Execution Claim 和 ToolExecutionService。所以接 MCP 时，我最重要的设计原则不是“把 MCP tools/call 跑起来”，而是避免再造一套执行链。
>
> 我们先把 MCP 定义成外部 Tool Provider。第一步只完成 Client 和 Discovery Boundary，通过 stdio 启动一个 MCP Server，在 application startup 阶段完成 initialize、capability negotiation、`notifications/initialized` 和分页 `tools/list`，得到一个 immutable discovery snapshot。Client 和每个 Server Session 都是 application scope，由现有 FastAPI lifespan 和 initialization stack 管生命周期。
>
> 安全方面，我们没有信任 Server 返回的 `readOnlyHint`、`idempotentHint` 这些 annotation，它们只属于 provider-declared metadata。真正的 risk、side effect、idempotency 和 approval 仍准备交给 LocalAgent 已有的 Adapter 和 Governance 决定。另外 MCP Server 本身是不可信外部进程，所以对 server 数、tool 数、pagination、JSON line、schema 大小和结构深度都有明确上限，子进程环境也不是直接继承完整父进程环境，避免 API Key 泄漏。
>
> Code Review 时还发现了一个很典型的生命周期 Bug：原来 server `kill()` 以后直接无界 `process.wait()`，恶意或异常子进程可能导致 LocalAgent shutdown 永久卡死。后来改成 stdin close、terminate、kill 三阶段共享 bounded close budget，最终不能确认退出就返回 failure，而不是无限等待。
>
> 当前这一 WP 只完成 discovery，还没有实现 `tools/call`，所以测试真实性标记是 deterministic fake stdio server，而不是 REAL_MCP_E2E。下一阶段才会把 MCP Tool 转成 MCP-backed ToolAdapter，进入已有 ToolRegistry、Governance、HITL 和 Execution Runtime。

------

# 11. 推荐学习文档名

```text
docs/interview/mcp_client_discovery_boundary.md
```

这份 WP 最值得重点记忆的三个面试关键词是：

```text
Provider Boundary（提供方边界）
Untrusted Metadata（不可信元数据）
Bounded Lifecycle（有界生命周期）
```

其中 **“MCP 是协议互操作边界，不是 Runtime Safety Authority”**，我认为是这一 WP 最值得你在面试中主动讲出来的一句话。