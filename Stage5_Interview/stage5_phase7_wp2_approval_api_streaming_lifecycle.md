当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase7-WP2 学习 / 面试总结

## Approval API / Streaming / Lifecycle（审批 API / 流式事件 / 生命周期）

WP2 最终状态：

```text
WP2_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

PUBLIC_API_CONTRACT = PASS
STREAMING_CONTRACT = PASS
PUBLIC_BINDING_BOUNDARY = PASS
HTTP_STATUS_TAXONOMY = PASS
DISCONNECT_TIMEOUT_BOUNDARY = PASS
PUBLIC_PAYLOAD_SAFETY = PASS
CUSTOM_ASGI_TEST_CREDIBILITY = PASS
WP1_RUNTIME_REGRESSION = PASS

BLOCKING_P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 4
PROCESS_VIOLATIONS = 0
ARCHITECTURE_REOPEN_REQUIRED = NO
READY_FOR_WP3 = YES
```

也就是说，WP2 没有重新设计 HITL Runtime，而是把 WP1 已经完成的审批核心可靠地暴露给客户端：**Streaming 负责观察，HTTP POST 负责命令，Runtime 继续拥有真实审批状态。**

------

# 1. 本 WP 解决什么问题

## 1.1 WP1 已经能审批，为什么还需要 WP2？

WP1 解决的是 Runtime 内部：

```text
Tool requires approval
    ↓
ToolApprovalController
    ↓
WAITING_FOR_APPROVAL
    ↓
APPROVE / REJECT
```

但它当时还是一个纯 Runtime capability（运行时能力）。

外部客户端并不知道：

```text
什么时候需要审批？
审批的是哪一次 Tool Invocation？
怎么告诉 Runtime“我批准”？
怎么告诉 Runtime“我拒绝”？
```

所以 WP1 结束时实际上只有：

```text
Python / Runtime domain command
```

还没有真正的：

```text
Client
→ Human
→ HTTP
→ Runtime
```

闭环。

------

## 1.2 WP2 补的核心缺口

WP2 把完整链路变成：

```text
High-risk Tool
        ↓
APPROVAL_REQUIRED
        ↓
WAITING_FOR_APPROVAL
        ↓
TOOL_APPROVAL_REQUESTED
        ↓
[[ORCH]] Streaming Event
        ↓
Client
        ↓
Human decides
        ↓
POST approve / reject
        ↓
RunRegistry
        ↓
ToolApprovalController
        ↓
WP1 Runtime lifecycle
```

因此 WP2 真正解决的是：

> **Transport Boundary（传输边界）如何接入 HITL Runtime，而不抢走 Runtime 的状态所有权。**

这是这一 WP 最核心的学习点。

------

# 2. 真实架构 / 数据流 / 状态流

## 2.1 最终双通道模型

WP2 采用的是：

> **Observation Channel（观察通道） + Command Channel（命令通道）**

### Observation Channel

已有：

```text
/api/chat
```

Streaming 流继续负责：

```text
Server
→ Client
```

传输 Runtime 事件。

新增两个公开事件：

```text
TOOL_APPROVAL_REQUESTED
TOOL_APPROVAL_DECIDED
```

仍然使用现有：

```text
[[ORCH]]{...}
```

格式，没有重新发明协议。

------

### Command Channel

人工决定使用独立：

```text
POST /api/runtime/runs/{run_id}/tool-approvals/{approval_id}/approve

POST /api/runtime/runs/{run_id}/tool-approvals/{approval_id}/reject
```

完成：

```text
Client
→ Server
```

方向的命令传输。

------

## 2.2 为什么这个设计很干净

整个架构可以看成：

```text
                    ┌──────── Observation ────────┐
                    │                              │
Runtime Event ──→ Stream Adapter ──→ Client / Human
                                           │
                                           │ Command
                                           ▼
                                      HTTP POST
                                           │
                                           ▼
                                      RunRegistry
                                           │
                                           ▼
                                ToolApprovalController
```

核心原则：

```text
Streaming
≠ Approval Owner

HTTP
≠ Approval Owner

RunRegistry
≠ Approval Owner
```

真正的 approval truth 仍然在：

```text
ToolApprovalController
```

所以 WP2 是：

> **Transport Integration（传输集成）**

而不是：

> 第二套 Approval Runtime。

------

# 3. 核心设计选择 / 候选方案 / 取舍

# 3.1 为什么不使用双向 SSE？

一种方案可以是：

```text
SSE connection
同时：
Server → Client
Client → Server
```

但 SSE 本质上就是：

> Server-Sent Events（服务器发送事件）

更天然是单向的。

WP2 没有强行把它变成双向协议，而是：

```text
SSE / stream
→ observation

HTTP POST
→ command
```

这能让两条职责清晰分开。

面试可以直接说：

> 我把 HITL 设计成 CQRS 风格的轻量分离：事件流负责 observation，HTTP command endpoint 负责 mutation，但 domain truth 仍然只在 Runtime。

这里可以类比 CQRS，但不要夸张成系统真的完整实现了 CQRS。

------

# 3.2 为什么不用一个通用 `/command` 接口？

候选：

```text
POST /api/runtime/command
{
    "type": "APPROVE",
    ...
}
```

看起来扩展性更强。

但它有几个问题：

```text
schema 过于泛化
route 语义不直观
客户端错误更难发现
authorization 未来更难按资源细分
容易逐渐变成万能命令总线
```

所以 WP2 选择资源化路径：

```text
/runs/{run_id}
/tool-approvals/{approval_id}
/approve
```

REST 风格更明确。

------

# 3.3 为什么 Approve 和 Reject 是两个 endpoint？

而不是：

```json
{
  "decision": "APPROVE"
}
```

一个原因是：

> decision 本身成为 route semantics（路由语义）。

这样 request body 只需要传 correlation 信息：

```json
{
  "invocation_binding_digest": "...",
  "actor_id": "..."
}
```

可以减少：

```text
decision 字段错误
非法 decision 值
schema ambiguity
```

也让审计更直观。

------

# 4. Public Binding（公共绑定）为什么不能用 raw invocation_id

这是 WP2 最关键的安全设计之一。

WP1 内部本来有：

```text
invocation_id
```

但 WP2 明确没有把 raw `invocation_id` 暴露给 HTTP 或 stream。

公开关联使用：

```text
run_id
+
approval_id
+
invocation_binding_digest
```



------

## 4.1 为什么只用 approval_id 不够？

如果 API 只传：

```text
approval_id
```

那么：

```text
知道 approval_id
```

的调用方理论上就能尝试做决定。

虽然本期依然没有真正 Authentication / Authorization，但至少可以额外要求：

```text
invocation_binding_digest
```

必须和当前 ApprovalRequest 精确对应。

------

## 4.2 为什么不用 tool_name？

因为：

```text
tool_name = update_config
```

可能存在：

```text
Invocation A
Invocation B
Invocation C
```

所以 tool name 完全不能唯一识别某一次执行。

------

## 4.3 为什么不用简单 identity digest？

Codex 在 WP2 冻结的 contract 里明确选择：

```text
invocation_binding_digest
```

而不是一个更弱的：

```text
invocation_identity_digest
```

因为完整 binding 还关联了：

```text
Tool
Arguments
Idempotency
Resource
Risk facts
```

因此公共命令是在说：

> “我要批准的是之前展示给我的这一个冻结调用。”

而不是：

> “我要批准叫这个 ID 的某个东西。”

------

# 5. Digest 不是 Authorization Token

这是面试很值得说的一点。

虽然 HTTP 需要：

```text
approval_id
+
invocation_binding_digest
```

但系统明确规定：

```text
invocation_binding_digest
!= credential
```

它只解决：

> Correlation / Integrity Binding（关联与完整性绑定）

不解决：

> Authentication / Authorization（身份认证 / 权限授权）

因此：

```text
知道 approval_id + digest
```

并不能被宣传成：

```text
这个用户有权批准
```

Final Gate 明确确认当前：

```text
HUMAN_DECISION_TRANSPORT = IMPLEMENTED

AUTHENTICATION = NOT_IMPLEMENTED
AUTHORIZATION = NOT_IMPLEMENTED
RBAC = NOT_IMPLEMENTED
```



------

# 6. HTTP Status Taxonomy（HTTP 状态分类）

这一部分非常适合面试。

系统没有把所有错误都变成：

```text
400
```

而是将 Runtime domain result 稳定映射为 HTTP。

------

## 6.1 第一次批准 / 拒绝

```text
200
```

说明 command 已被接受。

------

## 6.2 重复同一决定

例如：

```text
APPROVE
→ APPROVE
```

返回：

```text
200
idempotent = true
```

这意味着：

> 客户端因为重试重复发送请求是安全的。

这是 API Idempotency（接口幂等性）。

------

## 6.3 冲突决定

```text
APPROVE
→ REJECT
```

返回：

```text
409 Conflict
APPROVAL_DECISION_CONFLICT
```

因为：

> 资源存在，但当前请求与已经冻结的 decision 状态冲突。

非常符合 HTTP 409 语义。

------

## 6.4 Active Run 中 approval 不存在

```text
404
APPROVAL_UNKNOWN
```

意思是：

```text
Run 是活的
但这个 approval 找不到
```

------

## 6.5 Run 已不存在 / 终态

```text
410 Gone
APPROVAL_RUN_INACTIVE
```

为什么不是 404？

因为 transport 语义表达：

> 这个 active Run command surface 已经不存在。

`410 Gone` 比简单 404 更能表达生命周期结束。

------

## 6.6 Approval 已因 Cancel / Timeout 失效

```text
410
APPROVAL_INVALIDATED
```

同时 response 还能保留：

```text
INVALIDATED_CANCELLED
```

或者：

```text
INVALIDATED_TIMEOUT
```

这就是：

> Transport code + Domain status 双层表达。

------

# 7. Duplicate Request（重复请求）和 Idempotency

网络请求天然可能重试。

例如：

```text
Client
POST approve
    ↓
Server 成功
    ↓
Response 丢了
    ↓
Client 不知道成功
    ↓
再次 POST approve
```

如果第二次导致：

```text
Tool 再执行一次
```

就是严重问题。

WP2 保持了 WP1 的语义：

```text
same decision duplicate
→ 200
→ idempotent=true
→ no new Tool execution
```

Final Gate 真实验证：

```text
exactly one TOOL_STARTED
exactly one committed operation
```



所以必须区分：

```text
HTTP request can happen more than once

but

Tool side effect still happens at most once
```

------

# 8. 一个非常重要的真实 Bad Case：Invalidated vs Idempotent

这是 WP2 最值得讲的真实问题。

## Trigger

发生：

```text
APPROVE
    ↓
CANCEL
    ↓
late APPROVE
```

------

## 原错误行为

系统返回：

```text
200 idempotent
```

因为旧判断顺序是：

```text
if same decision:
    return idempotent success

if invalidated:
    return invalidated
```

于是虽然 Approval 已经被 Cancel invalidated，系统仍把 late approve 当成：

> “你之前已经批准过，所以还是成功。”



------

## 为什么危险？

因为：

```text
historically approved
```

和：

```text
currently effective approval
```

不是一回事。

系统可能曾经：

```text
APPROVED
```

但是：

```text
Cancel
```

已经撤销了继续执行资格。

------

## 修复

判断顺序改为：

```text
if INVALIDATED:
    return 410 APPROVAL_INVALIDATED

if same decision:
    return 200 idempotent
```

所以：

> **Lifecycle validity（生命周期有效性）优先于历史 decision idempotency。**

这是一个非常好的状态机 / API 联合设计案例。

------

# 9. Streaming Projection（流式投影）

WP2 没有把 Runtime Event 原样全部扔给客户端。

而是 explicit allowlist（显式白名单）。

------

## TOOL_APPROVAL_REQUESTED

公开：

```text
approval_id
tool_name
invocation_binding_digest
risk_level
risk_facts
```

不公开：

```text
raw invocation_id
raw args
arguments_digest
idempotency key
resource key
path
prompt
actor identity
```



------

## TOOL_APPROVAL_DECIDED

只公开：

```text
approval_id
invocation_binding_digest
decision_status
```

不公开：

```text
actor_id_digest
```

------

## 为什么需要 allowlist？

错误方案：

```python
payload.model_dump()
```

直接全部透出。

以后 Runtime 内部新增一个：

```text
filesystem_path
secret
raw_argument
```

字段，就可能自动暴露到客户端。

Explicit Projection（显式投影）可以保证：

> Public Contract 不随内部 Runtime DTO 自动膨胀。

------

# 10. Runtime Event 和 Streaming Event 的关系

非常重要：

客户端看到的：

```text
TOOL_APPROVAL_REQUESTED
```

不是 HTTP 层自己制造的 UI 事件。

真实链路是：

```text
Runtime event
    ↓
Journal-first publish
    ↓
Stream Adapter
    ↓
[[ORCH]]
    ↓
Client
```

所以：

> Streaming 是 Runtime Truth 的 Projection（投影）。

而不是第二套事实源。

Final Gate 专门确认 HTTP route 不会自己伪造审批事件。

------

# 11. Client Disconnect 为什么继续 Cancel Run

本阶段没有实现：

```text
Detached Run
Durable Execution
Reconnect
```

所以 `/api/chat` 仍然是：

> Request-owned streaming execution。

当 client disconnect：

```text
Client Disconnect
    ↓
ChatService watcher
    ↓
RunRegistry.cancel
    ↓
Run cancellation
    ↓
Approval invalidated
    ↓
worker wakes
    ↓
no Tool execution
```



------

## 为什么不在 WP2 顺手改成后台继续？

因为一旦：

```text
client disconnect
but Run keeps running
```

马上需要回答：

```text
Run 存哪里？
谁重新 attach？
怎么查询状态？
事件怎么 replay？
pending approval 怎么恢复？
server restart 怎么办？
```

这就不再是 Transport WP，而是：

> Durable Workflow Runtime。

所以继续接受 disconnect cancel 是合理 scope control。

------

# 12. Timeout 如何处理

Approval 等待仍然消耗：

```text
Run wall-clock deadline
```

所以：

```text
approval pending
→ deadline expired
→ approval invalidated
→ late approve = 410
```

没有额外引入：

```text
approval_timeout
approval_deadline
pause duration accounting
```

这继续保持 WP1 的简单 lifecycle。

------

# 13. Human-readable Context 的取舍

当前 Human 实际能看到：

```text
tool_name
risk_level
risk_facts
binding digest
```

但看不到：

```text
具体修改哪个文件
具体改成什么值
完整 tool args
```

这是当前一个明确 Accepted Limitation。

为什么没直接传 raw args？

因为：

```text
args
```

可能包含：

```text
filesystem path
credential
private content
prompt
resource identifiers
```

如果 WP2 为了“让人看懂”直接暴露 Tool args，就可能制造新的安全问题。

真正完善版本应该未来增加：

> Producer-owned Safe Approval Summary（生产者定义的安全审批摘要）

而不是让 Transport 层自己猜怎么脱敏。

------

# 14. 为什么 Transport 不应该负责 Redaction

假设 Tool：

```text
update_database
```

Transport 层只看到：

```text
args: {...}
```

它不知道：

```text
哪些字段敏感
哪些字段是业务关键
哪些字段用户应该看到
```

所以让 API 层做：

```text
generic redaction
```

很容易错。

更好的未来设计是：

```text
Tool / Policy Producer
→ SafeApprovalDisplay
→ Transport
```

也就是说：

> 安全显示内容应该尽可能由拥有业务语义的 producer 定义。

------

# 15. ASGI Streaming 测试为什么是一个很好的真实工程案例

WP2 实施时遇到一个很现实的问题：

```text
TestClient
httpx.ASGITransport
```

会整体 buffer streaming response。

所以想测试：

```text
读取 APPROVAL_REQUESTED
    ↓
在 Run 尚未结束时 POST approve
    ↓
继续读取 stream
```

会卡住。



------

## 为什么？

普通 TestClient 思路更像：

```text
Request
→ application completes
→ collect response
```

而 HITL 测试要求：

```text
Request A still running
        ↓
read partial response
        ↓
Request B modifies runtime
        ↓
Request A resumes
```

这是一个真正的并发交互场景。

------

## 最终方案

实施用了一个：

> same-event-loop minimal ASGI caller

直接：

```text
await app(scope, receive, send)
```

进入真实 FastAPI ASGI application。

Codex Final Gate 检查确认它真实经过：

```text
FastAPI routing
/api/chat
ChatService
Stream Adapter
approval HTTP route
RunRegistry
ToolApprovalController
AgentRouter
ToolExecutionService
```

并不是直接调用 Python route function。

------

## 为什么还保留官方 TestClient？

因为自定义 harness 容易漏掉：

```text
Pydantic validation
422
405
route schema
```

所以：

```text
Custom ASGI harness
→ 测实时 stream interaction

Official TestClient
→ 测 routing / validation / HTTP contract
```

两者组合比单独依赖一个更可信。

这是很好的测试架构设计案例。

------

# 16. Event Backward Compatibility（事件向后兼容）

WP2 给 Approval Event 增加了：

```text
invocation_binding_digest
```

但 WP1 已经可能写过没有这个字段的 Journal。

如果直接把它改成：

```text
required field
```

旧 Journal 可能无法读取。

所以 WP2 做成：

```text
新事件写入：
digest 必须存在

旧事件读取：
允许 digest 缺失
```



这是典型：

> **Write Strict, Read Compatible（写入严格、读取兼容）**

但这种兼容只针对已知历史字段，不是：

```text
allow arbitrary unknown field
```

unknown extra field 依旧 fail closed。

------

# 17. 真实性和完成边界

## 已实现

```text
HTTP approve endpoint
HTTP reject endpoint

strict request DTO
strict response DTO

run_id UUID validation
approval_id UUID validation
binding digest validation

public invocation binding

approval requested stream projection
approval decided stream projection

duplicate decision HTTP idempotency
decision conflict mapping

404 / 409 / 410 taxonomy

disconnect late command handling
timeout late command handling

actor_id audit label

legacy approval journal compatibility
```



------

## 已测试

Final Gate 重新执行：

```text
WP2 + WP1 focused:
75 passed
4 subtests passed
```

相关高价值回归：

```text
195 passed
4 subtests passed
```

并且：

```text
compileall PASS
git diff --check PASS
```

没有运行完整 3000+ full repository suite。

------

## Accepted P1

继续 4 项：

```text
restart 不恢复 pending

graceful shutdown 不恢复 pending

client disconnect cancels Run

approval wait 消耗 Run wall-clock deadline
```

------

## Accepted Limitations

```text
Authentication NOT IMPLEMENTED

Authorization NOT IMPLEMENTED

RBAC NOT IMPLEMENTED

no reconnect

no event replay

no status query

no detached execution

no human-readable argument summary

no approval UI

no notification

no Plan Approval

no Human Clarification
```



------

# 18. Real Bad Cases

## Bad Case 1 — Streaming TestClient 无法完成半双工 HITL

**真实性：IMPLEMENTATION_DISCOVERY**

### Trigger

希望：

```text
读取 stream 中 APPROVAL_REQUESTED
→ 发送 approve
→ stream 继续
```

### Symptom

TestClient / ASGITransport 缓冲 response。

Run 不结束：

```text
client 就读不到 chunk
```

### Root Cause

测试 transport 更偏 request-response，而测试需要 concurrent streaming interaction。

### Fix

使用：

```text
same-event-loop ASGI caller
```

做真实生产 app 的实时交互测试，同时保留 TestClient 做标准 validation。

### Knowledge Point

> 测试 ASGI streaming 时，“ASGI-level”并不自动意味着支持实时双向交互。



------

# Bad Case 2 — Router Stub 缺方法导致 Generic Step Failure

**真实性：TEST_FAILURE**

### Trigger

测试 driver router 缺少：

```text
calls_for_agent
```

### Symptom

外部只看到：

```text
AGENT_STEP_FAILED
```

而没有原始 AttributeError。

### Root Cause

Adapter boundary 把底层异常统一包装成 Step Failure。

### Fix

补齐测试 stub。

### Knowledge Point

> 在多层 Runtime 中，错误经过 Adapter 后往往会被归一化，诊断时不能只看最外层错误码。



------

# Bad Case 3 — Late Approve 错误返回 200

**真实性：IMPLEMENTATION_DISCOVERY**

这个是 WP2 最值得讲的。

### Trigger

```text
APPROVE
→ CANCEL
→ APPROVE again
```

### Symptom

第二个 Approve 返回：

```text
200 idempotent
```

### Root Cause

代码先判断：

```text
same decision
```

再判断：

```text
invalidated
```

### Risk

客户端会认为 Approval 依然有效。

### Fix

优先：

```text
INVALIDATED
```

判断。

### Regression

最终：

```text
late approve
→ 410 APPROVAL_INVALIDATED
```

### Knowledge Point

> Idempotency 只有在目标状态仍然有效时才成立；生命周期失效优先级高于重复请求语义。



------

# Bad Case 4 — Cross-binding Test 错误构造了第二个 Approval

**真实性：TEST_FAILURE**

### Trigger

为了测试不同 Invocation B，直接在同一个 Waiting Step 创建第二个 approval。

### Symptom

状态机报：

```text
WAITING_FOR_APPROVAL
不允许 APPROVAL_REQUESTED
```

### Root Cause

一个 active Step 在当前 Contract 下只有一个 approval wait slot。

### Fix

不创建第二个 Approval，而是直接计算 B 的真实：

```text
invocation_binding_digest
```

然后向 Approval A 提交错误 digest。

### Knowledge Point

> 测试 Bad Case 时也必须遵守被测试系统真实状态机，否则测到的是非法测试构造，而不是目标安全边界。



------

# 19. 名词 / 概念速览

**Transport Layer（传输层）**：负责请求、响应和数据传输，不拥有业务状态。

**Observation Channel（观察通道）**：用于服务端向客户端暴露状态或事件。

**Command Channel（命令通道）**：客户端向 Runtime 提交会改变业务状态的命令。

**Public Contract（公共合同）**：外部客户端可依赖的稳定 API/schema/error semantics。

**DTO（Data Transfer Object，数据传输对象）**：专门用于接口层传输的数据结构，与内部领域对象解耦。

**Correlation（关联）**：将客户端看到的事件与后续提交的 command 对应到同一业务对象。

**Invocation Binding Digest（调用绑定摘要）**：对冻结 Tool Invocation 安全绑定事实计算的 digest，用于防止 command 作用到错误调用。

**Idempotent Request（幂等请求）**：重复发送相同请求不会产生额外业务副作用。

**HTTP 409 Conflict（冲突）**：请求与当前资源状态冲突，例如先 APPROVE 后 REJECT。

**HTTP 410 Gone（已失效）**：资源或生命周期对象已经失效，不再能够接受该操作。

**Allowlist Projection（白名单投影）**：仅明确允许的字段才能进入公共输出。

**Request-owned Execution（请求所有执行）**：Runtime 生命周期依附原始客户端请求，断开请求会取消执行。

**ASGI（Asynchronous Server Gateway Interface，异步服务器网关接口）**：Python 异步 Web Server 与应用之间的标准协议。

**Authentication（身份认证）**：确认“你是谁”。

**Authorization（权限授权）**：确认“你能做什么”。

**RBAC（Role-Based Access Control，基于角色的访问控制）**：根据角色管理权限。

**Backward Compatibility（向后兼容）**：新版本仍能正确处理旧版本已经产生的数据或协议。

**Write Strict, Read Compatible（写严格、读兼容）**：新数据必须遵守最新 schema，而历史数据可以按明确兼容规则读取。

------

# 20. 工程构建方法类问答

## Q1：为什么 HTTP API 不直接改 AgentState？

因为：

```text
HTTP
```

只是 transport。

如果 route 可以直接：

```text
StepStatus = RUNNING
```

那么：

```text
Runtime domain command
HTTP
内部 worker
```

都会成为状态修改者。

最终失去：

> Single Source of Truth（单一事实来源）。

因此必须：

```text
HTTP
→ RunRegistry
→ ToolApprovalController
→ AgentStateMachine
```

------

## Q2：为什么 Streaming Event 不能直接 `model_dump()`？

因为内部 payload 未来可能增加敏感字段。

公共 API 一旦全量自动序列化：

```text
内部字段增加
→ public API 自动增加
```

就会破坏：

```text
安全边界
API compatibility
```

因此要 explicit allowlist。

------

## Q3：为什么 inactive Run 返回 410 而不是 404？

404 更像：

> 找不到资源。

410 更适合：

> 这个 Runtime command target 已经失效。

对于：

```text
Run 已结束
```

场景，410 能更明确表达 lifecycle。

------

## Q4：为什么重复 Approve 返回 200？

网络天然可能重试。

如果同一个 approve 已经生效：

```text
重复 approve
```

不应该被当成系统错误。

只要保证：

```text
no new state change
no second execution
```

就可以返回：

```text
200 + idempotent=true
```

------

## Q5：为什么 Approve 后 Reject 是 409？

因为这不是：

```text
请求格式错误
```

而是：

```text
当前资源状态与命令冲突
```

所以用 409 很自然。

------

## Q6：为什么 binding digest 不能当权限 token？

因为它证明的是：

```text
你引用的是哪一个 invocation
```

而不是：

```text
你是谁
你有没有批准权限
```

所以 Integrity/Correlation 和 Authorization 必须分开。

------

## Q7：为什么还不做 Authentication / RBAC？

因为当前阶段目标是：

```text
Minimum Credible HITL
```

现有 deployment 主要是本机 loopback。

如果现在加：

```text
JWT
OAuth
RBAC
multi-user principal
```

会显著扩大 scope。

但不能因此说当前 API 已经安全支持非可信网络。

------

## Q8：为什么不能直接把 raw Tool args 给 Human 看？

因为 args 可能包含敏感数据。

如果没有明确：

```text
safe display schema
```

Transport 层不应该自行决定哪些字段安全。

------

# 21. 高频面试追问

建议重点准备：

1. HITL 为什么要区分 observation 和 command？
2. 为什么 Approval API 不直接操作 AgentState？
3. `approval_id` 为什么不够？
4. 为什么公共 API 不暴露 raw invocation ID？
5. invocation binding digest 解决什么问题？
6. digest 为什么不是 authorization token？
7. duplicate approve 为什么返回 200？
8. approve 后 reject 为什么返回 409？
9. active unknown approval 和 inactive run 为什么分别是 404/410？
10. Cancel 后 late approve 为什么不能继续返回 idempotent 200？
11. Streaming event 为什么必须显式 allowlist？
12. 为什么 Runtime Event 才是事实，而 HTTP/stream 只是 projection？
13. Client disconnect 为什么当前会 cancel Run？
14. 怎么做真正的 detached execution？
15. 为什么当前没有 reconnect/replay？
16. 为什么不显示 raw Tool arguments？
17. Authentication 和 Authorization 的区别？
18. Loopback 是否等于安全认证？
19. ASGI streaming 为什么难测？
20. TestClient 和真实 streaming interaction 有什么区别？
21. 如何做旧 Journal schema compatibility？
22. 为什么采用“写严格、读兼容”？

------

# 22. 30 秒面试总结

> 在 HITL Runtime Core 完成后，我进一步实现了审批 Transport。服务端继续使用原来的 `[[ORCH]]` streaming 作为 observation channel，向客户端发送 `TOOL_APPROVAL_REQUESTED` 和 `TOOL_APPROVAL_DECIDED`；客户端通过独立的 approve/reject HTTP endpoint 提交人工决定。API 不拥有审批状态，只通过 RunRegistry 转发给 Runtime 的 ToolApprovalController。公共关联不暴露 raw invocation ID，而使用 `run_id + approval_id + invocation_binding_digest`，并通过显式 allowlist 防止 Tool 参数等敏感信息进入 stream。接口还定义了稳定的 200/404/409/410 状态语义，重复 approve 是幂等 200，而失效 approval 的 late command 返回 410。当前明确没有 Authentication/RBAC，因此这是 Minimum Credible HITL transport，而不是完整生产级审批权限系统。

------

# 23. 2 分钟面试总结

> WP1 做完以后，LocalAgent Runtime 内部已经能进入 `WAITING_FOR_APPROVAL`，也有安全的 approve/reject 和 execution claim，但客户端实际上还不知道什么时候需要人工操作，也没有公共命令接口。所以 WP2 主要解决 Transport Boundary。
>
> 我没有让 HTTP 或 Streaming 成为第二套状态 Owner，而是设计成两个通道：`/api/chat` 原有 streaming 负责 observation，独立 POST endpoint 负责 command。Runtime 产生 `TOOL_APPROVAL_REQUESTED` 后，经 Journal-first 和 Stream Adapter 以 `[[ORCH]]` 控制事件发给客户端；客户端再调用 `/approve` 或 `/reject`，HTTP 只做 DTO 校验和结果投影，最终仍然转发到 RunRegistry 和 ToolApprovalController。
>
> 安全上，公共 API 不暴露 Runtime 内部 raw `invocation_id`，而使用 `run_id + approval_id + invocation_binding_digest`。Streaming 也使用 explicit allowlist，只展示 tool name、risk level、risk facts 和 binding digest，不自动 dump Runtime payload，避免内部字段变更造成敏感信息泄漏。
>
> API 还设计了稳定的状态语义：相同 decision 重试返回 200/idempotent，approve 后 reject 返回 409，active Run 内 unknown approval 返回 404，Run 已终止或 approval 已失效返回 410。
>
> 实施中一个很有价值的 Bad Case 是 `approve → cancel → late approve`。最初代码先判断 same-decision，所以 late approve 会错误返回 200；后来改成 lifecycle invalidation 优先，失效后的 command 必须返回 410。这让我更明确地认识到幂等只针对仍然有效的状态。
>
> Streaming 测试也遇到了 TestClient buffering 问题，所以使用了真实 ASGI app 的 same-event-loop caller 测 pending stream interaction，同时保留官方 TestClient 测 routing 和 schema validation。
>
> 最终 WP2 是 `PASS_WITH_ACCEPTED_LIMITATIONS`，Blocking P1 为 0。目前真实实现了 human decision transport，但 Authentication、Authorization、RBAC、Reconnect 和 Durable Resume 都没有实现，我会在面试中明确这个边界。

------

# 24. 推荐继续深入的关键词

这一 WP 面试价值最高的关键词：

```text
REST API Design
HTTP Status Semantics

Idempotent API
Idempotency

Public API Contract
DTO
Schema Validation

Observation vs Command

Streaming API
SSE
ASGI

Correlation ID
Integrity Binding

Authentication
Authorization
RBAC

Data Redaction
Public Payload Safety

Backward Compatibility
Schema Evolution

Request-owned Execution
Detached Execution
Durable Workflow
```

其中优先学习：

```text
HTTP 404 / 409 / 410
Idempotent API
Authentication vs Authorization
ASGI Streaming
Schema Evolution
Explicit Allowlist
```

------

# 25. 推荐学习文档文件名

```text
docs/interview/stage5_phase7_wp2_approval_api_streaming_lifecycle.md
```

WP2 的学习 / 面试总结到这里完成。

按照我们固定规则，我继续停在 WP2 边界，**不自动进入 WP3**。