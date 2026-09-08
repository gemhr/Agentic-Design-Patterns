当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase7-WP4 学习 / 面试总结

## Minimal Approval UI Closure（最小审批 UI 闭环）

WP4 最终状态：

```text
WP4_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

APPROVAL_CARD = PASS
STREAM_REQUESTED_HANDLING = PASS
STREAM_DECIDED_HANDLING = PASS
APPROVE_COMMAND = PASS
REJECT_COMMAND = PASS
UI_THREAD_SAFETY = PASS
HTTP_STREAM_RACE_BOUNDARY = PASS
RUN_SCOPED_TERMINAL_CLEANUP = PASS
WIDGET_LIFECYCLE = PASS
PUBLIC_PAYLOAD_SAFETY = PASS

BACKEND_CONTRACT_UNCHANGED = YES

BLOCKING_P0 = 0
BLOCKING_P1 = 0
PROCESS_VIOLATIONS = 0
ARCHITECTURE_REOPEN_REQUIRED = NO

PHASE7_UI_CLOSURE = PASS
```

WP4 的定位非常清楚：**不增加新的 HITL Runtime 能力，而是把 WP1/WP2 已存在的审批能力变成人真正可以在桌面客户端“看见并操作”的产品闭环。**

------

# 1. 本 WP 解决什么问题

WP1 已经解决 Runtime：

```text
High-risk Tool
→ WAITING_FOR_APPROVAL
→ APPROVE / REJECT
```

WP2 已经解决 Transport：

```text
Runtime
→ stream approval event
→ HTTP approve/reject
→ Runtime
```

但用户真实使用时还缺一层：

```text
用户怎么看到 approval？
用户在哪里点击 Approve？
用户在哪里点击 Reject？
审批失效后 UI 怎么反馈？
```

所以 WP4 补齐：

```text
TOOL_APPROVAL_REQUESTED
        ↓
Desktop Client
        ↓
Approval Card
        ↓
Human Approve / Reject
        ↓
existing HTTP API
        ↓
Runtime
        ↓
TOOL_APPROVAL_DECIDED
        ↓
Card terminal state
```

最终 Phase7 的准确能力范围因此扩展成：

```text
MINIMUM_CREDIBLE_TOOL_APPROVAL_HITL
+
HUMAN_FACING_UI_CLOSURE
```

但仍然不是 Production Approval Platform。

------

# 2. 真实架构 / 数据流 / 状态流

最终 UI 数据链：

```text
LocalAgent Runtime
        ↓
Journal-first Runtime Event
        ↓
[[ORCH]]
        ↓
ApiWorker
        ↓
status_signal
        ↓
MainController
        ↓
ChatPanel.handle_approval_event()
        ↓
ApprovalCardWidget
```

人工点击以后：

```text
ApprovalCardWidget
        ↓ Qt signal
MainController
        ↓
background short-request thread
        ↓
approve / reject HTTP API
        ↓
Runtime
        ↓
approval_result_signal
        ↓
MainController UI thread
        ↓
Approval Card update
```

同时 Runtime 还会通过 stream 回传：

```text
TOOL_APPROVAL_DECIDED
```

最终：

```text
HTTP result
+
stream event
```

共同驱动 UI presentation，但 **Runtime truth 仍然只在后端。**

------

# 3. 核心设计选择 / 方案取舍

## 3.1 为什么采用聊天流里的 Approval Card

而不是独立：

```text
Approval Center
```

因为当前目标是最小实现。

聊天流天然已经存在：

```text
User message
Assistant
Runtime event
Tool result
```

所以审批也作为 timeline element：

```text
User
Assistant
Approval Card
Tool
Assistant
```

不需要再构建：

```text
global approval store
history page
pending center
notification subsystem
```

这就是典型的 Scope Control（范围控制）。

------

## 3.2 为什么不用 Modal Dialog

Modal dialog 容易带来：

```text
阻塞交互
生命周期更复杂
多 approval 冲突
window ownership
```

而 timeline card：

```text
非阻塞
天然保存上下文
适合多个 approval
更适合 Agent 对话产品
```

因此更符合当前桌面 Agent 架构。

------

## 3.3 为什么 UI 不重新实现 Approval State Machine

UI 只维护：

```text
PENDING
SUBMITTING
APPROVED
REJECTED
EXPIRED
ERROR
```

这些叫：

> Presentation State（展示状态）

它们不是：

```text
ApprovalStatus
StepStatus
RunStatus
```

UI 不知道：

```text
EXECUTION_CLAIMED
controller CAS
worker lifecycle
```

也不应该知道。

核心原则：

> **Frontend Presentation State != Runtime Business State**

------

# 4. 为什么点击 Approve 不能立即显示“已批准”

用户点击按钮只是：

```text
User Intent
```

不是 Runtime Fact。

例如点击 Approve 后可能发生：

```text
Run already timeout
approval invalidated
binding mismatch
opposite decision already won
Run inactive
network error
```

所以正确流程：

```text
PENDING
   ↓ click
SUBMITTING
   ↓
HTTP / Stream result
   ↓
APPROVED / REJECTED / EXPIRED / ERROR
```

而不是：

```text
click
→ APPROVED
```

这与整个 Phase7 的原则保持一致：

> **Transport/UI 不拥有 Runtime Truth。**

------

# 5. 为什么 HTTP 和 Stream 两条反馈都需要

WP2 本来就是双通道：

```text
Command Channel:
HTTP

Observation Channel:
stream
```

WP4 延续这一设计。

## HTTP

回答：

> “我刚才提交的 command 被怎么处理了？”

例如：

```text
200
409
410
network error
```

## Stream

回答：

> “Runtime 当前观察到的 lifecycle 是什么？”

例如：

```text
TOOL_APPROVAL_DECIDED(APPROVED)
```

所以可以理解：

```text
HTTP = command acknowledgement

Stream = runtime lifecycle observation
```

------

# 6. WP4 最重要的问题之一：HTTP / Stream Race

因为两条通道并发，所以事件顺序不固定。

## 场景 A：HTTP 先回来

```text
click Approve
→ HTTP 200
→ UI APPROVED
→ stream APPROVED
```

stream 只做：

```text
idempotent confirm
```

------

## 场景 B：Stream 先回来

```text
click Approve
→ SUBMITTING
→ stream APPROVED
→ UI APPROVED
→ HTTP 200 later
```

HTTP 不能把状态改坏。

------

## 更危险：Stream terminal 后 HTTP error

Final Gate 专门补测：

```text
stream APPROVED
→ late network error
```

最终仍必须：

```text
APPROVED
```

不能：

```text
APPROVED → ERROR
```



这体现一个非常重要的 UI 合并规则：

> **Terminal Runtime Observation wins over late Transport Result。**

------

# 7. 另一条关键 Race：Invalidated 后 Late HTTP Success

例如：

```text
SUBMITTING
→ timeout
→ stream INVALIDATED_TIMEOUT
→ UI EXPIRED
→ HTTP 200 late
```

正确最终状态：

```text
EXPIRED
```

而不是：

```text
APPROVED
```

Final Gate 已补直接回归测试。

所以可以抽象为一个 precedence：

```text
Runtime terminal event
>
late HTTP result
>
intermediate UI state
```

------

# 8. Qt UI Thread Safety（Qt UI 线程安全）

这是 WP4 最重要的工程知识之一。

HTTP 请求不能：

```python
button_clicked():
    requests.post(...)
```

直接运行在 UI thread。

否则网络稍慢，整个窗口都会卡住。

当前设计：

```text
UI Thread:
click
→ disable buttons

Background Thread:
HTTP POST

Qt Signal:
approval_result_signal

UI Thread:
update widget
```

Final Gate 确认后台 daemon thread：

- 只进行 HTTP；
- 不调用 QWidget；
- 不操作 layout；
- 不直接修改 card；
- 最终通过 signal 返回 `MainController` 的 UI thread affinity。

------

# 9. 为什么线程不能直接改 QWidget

Qt 的核心规则之一：

> QWidget 应由 GUI thread 操作。

如果 worker thread 做：

```text
widget.setText()
widget.setEnabled()
layout.addWidget()
```

可能出现：

```text
随机 crash
未定义行为
竞态
难复现 UI bug
```

所以：

```text
worker
→ signal
→ UI thread
```

是标准模式。

------

# 10. Double Click（重复点击）怎么处理

后端已经支持：

```text
duplicate approve = idempotent
```

但前端仍然做：

```text
PENDING
→ click
→ SUBMITTING
→ disable approve/reject
```

第二次 click：

```text
no HTTP request
```

为什么后端既然安全，前端还要做？

因为：

> Backend Idempotency 是安全最后防线，不代表 Frontend 应主动制造重复 command。

这属于：

> Defense in Depth（纵深防御）。

------

# 11. Correlation（关联）

每张 Approval Card 的主 key：

```text
(run_id, approval_id)
```

内部保存：

```text
invocation_binding_digest
```

点击当前卡片时，从**当前 Card model**读取：

```text
run_id
approval_id
binding digest
```

而不是：

```text
current approval
latest approval
global current run approval
```

Final Gate 特别确认：

> Approval A 不会错误发送 Approval B 的 correlation。

------

# 12. 为什么 Duplicate Requested 不能生成第二张 Card

Stream 理论上可能重复投影同一：

```text
run_id + approval_id
```

如果 UI 每次都：

```text
new ApprovalCardWidget()
```

就会出现：

```text
同一个 Approval
→ 两组 Approve/Reject 按钮
```

虽然后端最终仍有 CAS，但 UX 会非常混乱。

所以 presentation 层也做幂等：

```text
same key
→ consume / update existing
→ no duplicate action surface
```

------

# 13. Run-scoped Cleanup（按 Run 清理）

当：

```text
Run A
```

结束时，只应该：

```text
expire Run A pending cards
```

不能影响：

```text
Run B
```

Final Gate 新增了 cross-run regression：

```text
Run A terminal
→ Run A card EXPIRED
→ Run B pending remains unchanged
```



这是一个很好的状态隔离问题。

------

# 14. 为什么 Stream Settled 也要 Cleanup

可能发生：

```text
Approval Card PENDING
```

但由于：

```text
stream closed
worker settled
run terminal
```

后续已经没有机会收到新的 approval lifecycle event。

如果卡片仍然：

```text
Approve enabled
Reject enabled
```

用户就会点击一个已经失去 Run context 的按钮。

因此：

```text
stream settled
→ pending approval cards EXPIRED
```

这是 UI lifecycle 和 Runtime lifecycle 对齐的一部分。

------

# 15. Widget / Callback Lifecycle（控件与回调生命周期）

另一个典型异步 UI 问题：

```text
HTTP request starts
        ↓
user resets chat
        ↓
widget removed
        ↓
HTTP callback arrives
```

如果 callback 还持有：

```text
direct QWidget pointer
```

可能：

```text
access deleted object
crash
```

当前实现没有让 worker 持有 widget。

而是回调后：

```text
(run_id, approval_id)
→ lookup model/card
```

如果已经不存在：

```text
no-op
```

Final Gate 确认这一点。

------

# 16. 一个很好的真实 Bad Case：Optional Cleanup Guard

ZCode 为了兼容旧测试 fake，最初写了类似：

```python
cleanup = getattr(chat_panel, "expire_pending_approvals", None)

if callable(cleanup):
    cleanup(...)
```

表面上很健壮。

但 Codex Final Gate 指出：

> 生产 `ChatPanel` 本来就是固定 Composition，cleanup 是必须能力。

如果生产代码忘记实现：

```text
expire_pending_approvals()
```

这个 guard 会：

```text
静默跳过
```

最终导致：

```text
stale Approval Card
仍然可点击
```

这是一个典型：

> **Over-defensive Coding（过度防御式编码）掩盖 Contract Bug**

最终 fix-forward：

```text
生产代码明确调用 cleanup
测试 fake 补齐相同 interface
```

而不是削弱生产合同。

------

# 17. 这个 Bad Case 的通用知识

很多人会认为：

```python
getattr(obj, "method", None)
```

越多越健壮。

其实不一定。

如果某个 method 是：

> Required Interface（必选接口）

那么缺少 method 就应该：

```text
fail fast
```

而不是：

```text
silent ignore
```

所以要区分：

```text
Optional Capability
```

和：

```text
Required Composition Contract
```

这是很适合后端 / Agent / UI 系统设计面试讲的工程细节。

------

# 18. Public Payload Safety（公共数据安全）

UI 只展示：

```text
tool_name
risk_level
risk_facts
fixed human message
```

内部可以保存：

```text
run_id
approval_id
binding digest
```

但不展示 digest。

完全不展示：

```text
raw invocation ID
raw arguments
filesystem path
prompt
secret
resource content
exception
internal error code
```

Final Gate 还进行了源码搜索确认。

------

# 19. 为什么 UI 不展示 Binding Digest

虽然：

```text
invocation_binding_digest
```

在 Public Contract 中是安全 correlation 字段，

但它对用户没有可解释价值。

所以：

```text
safe to expose
```

不等于：

```text
worth showing
```

UI 层还需要考虑：

> Human Usability（人类可用性）。

这是 Public API 和 UX 的区别。

------

# 20. Human-readable Approval Context 仍然没解决

当前卡片能告诉用户：

```text
Tool: update_config
Risk: HIGH
Risk facts:
- destructive_write
```

但不能告诉：

```text
准备修改哪个配置？
从什么值改成什么值？
具体副作用是什么？
```

原因是后端目前没有 producer-owned：

```text
SafeApprovalSummary
```

WP4 没有偷偷把：

```text
raw args
```

塞进 UI，因此没有突破 Phase7 Security Boundary。

这属于一个应如实承认的限制。

------

# 21. HTTP Error 如何映射成 UI

## 409

例如：

```text
decision conflict
binding mismatch
```

用户看到：

> 审批状态已发生变化，请以当前运行状态为准。

而不是：

```text
APPROVAL_BINDING_MISMATCH
```

------

## 404 / 410

表示 Approval 或 Run 已失效：

```text
→ EXPIRED
→ disable buttons
```

------

## Network Failure

```text
→ ERROR
```

如果没有收到 terminal Runtime event：

允许用户明确 retry。

但一旦：

```text
APPROVED
REJECTED
EXPIRED
```

就永远不能重新 enable。



------

# 22. UI 为什么不能直接显示 exception

例如：

```text
requests.ConnectionError(...)
```

可能包含：

```text
host
port
internal URI
stack details
```

甚至未来可能包含敏感 response。

所以：

```text
low-level exception
→ safe error result
→ human-readable UI message
```

这与 Backend Error Projection 是同一个设计思想。

------

# 23. 真实性与完成边界

## 已真实实现

```text
Approval Card

TOOL_APPROVAL_REQUESTED → Card

duplicate Requested idempotency

Approve button

Reject button

correct HTTP route

binding digest command body

button submit disable

background HTTP thread

Qt signal/slot result dispatch

TOOL_APPROVAL_DECIDED → terminal state

HTTP/stream race protection

Run terminal cleanup

cross-run cleanup isolation

late callback lifecycle safety

public payload safety
```



------

## 已真实测试

Focused：

```text
65 passed
1 warning
```

包括：

```text
approval presentation
cancellation client
ApiWorker
chat stream compatibility
approval stream projection
approval HTTP API
capability docs
security docs
```

同时：

```text
compileall = PASS
git diff --check = PASS
```

没有运行 full suite，也没有启动真实 backend。

------

# 24. Accepted Limitations

仍然没有：

```text
Authentication
Authorization
RBAC

reconnect / replay

pending approval center

approval history

notification

restart recovery

human-readable argument summary

Plan Approval

Human Clarification
```



这些都没有阻塞 WP4。

------

# 25. Real Bad Case 1 — `pyqtSignal` Import 遗漏

**真实性：TEST_FAILURE**

### Trigger

首次增加：

```text
ApprovalCardWidget
```

### Symptom

测试 collection 阶段失败。

### Root Cause

遗漏：

```text
pyqtSignal
```

import。

### Fix

补 import。

### Regression

Focused suite PASS。

### Knowledge Point

> UI component 改动不仅要测交互逻辑，也要至少进行模块 import / collection smoke。

------

# 26. Real Bad Case 2 — Test Fake 没实现新 Interface

**真实性：TEST_FAILURE**

### Trigger

`MainController` 增加：

```text
expire_pending_approvals()
```

调用。

### Symptom

旧 `test_api_worker.py` 的 fake `chat_panel` 没这个方法。

### 初版修复

生产代码使用 optional `callable` guard。

### Final Gate 判断

这会削弱生产 Composition Contract。

### 最终 Fix

```text
production:
explicit cleanup call

test fake:
implement required capability
```

### Knowledge Point

> Test Double（测试替身）应该跟随 production required interface，而不是反过来削弱 production contract。



------

# 27. Real Bad Case 3 — 缺少 Terminal-vs-Late-HTTP Race 回归

**真实性：CODEX_GATE_DISCOVERY**

实现本身已有 terminal-state protection，

但测试没有直接覆盖：

```text
APPROVED
→ late network error
```

和：

```text
INVALIDATED_TIMEOUT
→ late HTTP success
```

Final Gate 补了两个 regression。

### Knowledge Point

> 并发系统不能只测试“正常顺序”和“反向顺序”，还要测试不同通道产生相互冲突结果时的 authority precedence。



------

# 28. Real Bad Case 4 — Cross-run Cleanup Coverage Gap

**真实性：CODEX_GATE_DISCOVERY**

原实现声明：

```text
terminal cleanup scoped by run_id
```

但测试没有直接证明：

```text
Run A cleanup
```

不会：

```text
expire Run B
```

Final Gate 增加 regression。

### Knowledge Point

> 只要状态 key 里包含 scope ID，就应该针对 scope isolation 写一个直接 negative test。

------

# 29. 名词 / 概念速览

**Human-facing Closure（面向人的闭环）**：把已经存在的后端能力真正暴露成用户可以感知和操作的交互。

**Presentation State（展示状态）**：只描述 UI 当前表现，不作为业务真实状态。

**Runtime Truth（运行时事实）**：后端 Runtime 对真实业务生命周期拥有的权威状态。

**Qt Event Loop（Qt 事件循环）**：负责 GUI event dispatch 和界面刷新，不能被同步网络 I/O 阻塞。

**Signal / Slot（信号 / 槽）**：Qt 的线程间和组件间事件通信机制。

**Thread Affinity（线程亲和性）**：QObject 所归属的线程上下文。

**Race Condition（竞态条件）**：多个异步事件顺序不同导致结果不一致的问题。

**Terminal State（终态）**：生命周期已经结束、不应被后续中间状态覆盖的状态。

**Idempotent UI Projection（幂等 UI 投影）**：同一 Runtime event 重复出现时不会创建重复 UI 或改变已经一致的结果。

**Run-scoped Cleanup（按 Run 范围清理）**：只清理属于目标 Run 的 UI 状态。

**Test Double（测试替身）**：测试中代替真实依赖的 fake / stub / mock。

**Composition Contract（组装合同）**：生产组件之间必须提供的接口能力约定。

**Fail Fast（快速失败）**：必需能力缺失时立即暴露错误，而不是静默忽略。

**Defense in Depth（纵深防御）**：即使后端已有安全保护，前端仍增加合理的本地保护。

------

# 30. 工程构建方法类问答

## Q1：为什么 UI 不能直接调用 Runtime Controller？

因为：

```text
UI
```

只是外部客户端。

必须遵循：

```text
UI
→ HTTP Public Contract
→ RunRegistry
→ Runtime
```

否则桌面端与 Runtime internal architecture 强耦合。

------

## Q2：为什么还要保留 HTTP，而不是 stream 双向操作？

Stream 当前承担：

```text
server → client
```

HTTP command 承担：

```text
client → server
```

职责明确，且复用了已经冻结的 WP2 contract。

------

## Q3：为什么 UI presentation state 不应该复制 Runtime state？

否则 UI 会成为第二个状态机。

出现：

```text
Runtime APPROVED
UI PENDING
```

时，你就需要做复杂 reconciliation。

UI 只需要表达用户体验，不应该重新定义业务状态。

------

## Q4：为什么 stream terminal 应优先于 HTTP callback？

因为 stream 表示：

```text
Runtime lifecycle observation
```

而 HTTP callback 可能只是较早 command 的延迟结果。

例如 Runtime 已 timeout：

```text
EXPIRED
```

late HTTP success 不应复活 UI。

------

## Q5：为什么 button disabled 仍然重要？

后端已经有 CAS 和 idempotency。

但 UI 本地避免重复 command：

```text
提升 UX
减少请求
减少日志噪声
降低 race 频率
```

同时仍保留 Backend Safety。

------

## Q6：为什么使用 `(run_id, approval_id)` 做 UI key？

因为：

```text
approval_id
```

属于一个具体 Run。

把 Run scope 也编码进 key：

有利于：

```text
isolation
cleanup
multi-run correctness
```

------

## Q7：为什么不能为了兼容 fake 加 optional guard？

如果 production dependency 本来就必须实现该方法，

optional guard 会把：

```text
Composition Bug
```

变成：

```text
Silent Functional Loss
```

正确做法是：

```text
更新 fake
```

而不是削弱生产接口。

------

# 31. 高频面试追问

建议准备：

1. 为什么 HITL 还需要前端 Closure？
2. UI 和 Runtime 谁拥有 Approval truth？
3. 为什么点击批准不能立即显示已批准？
4. HTTP result 和 stream event 谁更权威？
5. stream event 和 HTTP callback 顺序不固定怎么办？
6. 为什么 terminal state 不能被 late HTTP error 覆盖？
7. Qt 为什么不能在 UI thread 发同步 HTTP？
8. Qt worker 如何安全更新 QWidget？
9. Signal/Slot 在这里解决什么？
10. 如何处理 window/chat reset 后 late callback？
11. 为什么要用 `(run_id, approval_id)` 做 correlation？
12. duplicate Requested 怎么处理？
13. Run A terminal 为什么不能清理 Run B？
14. 后端已经幂等，为什么前端还禁用按钮？
15. HTTP 409 和 410 在 UI 怎么区别？
16. 为什么不能把 internal error code 直接展示？
17. 为什么不展示 raw Tool arguments？
18. 为什么当前 Approval Card 仍然只能显示 risk facts？
19. Test fake 缺接口为什么不应该用 `getattr` 糊过去？
20. UI 加完以后 HITL 的完整用户路径是什么？

------

# 32. 30 秒面试总结

> 在 HITL Runtime 和 approve/reject API 完成后，我补了一个最小 PyQt 审批 UI，让高风险 Tool 触发后会在聊天时间线里生成 Approval Card，展示 tool name、risk level 和 risk facts，用户可以直接批准或拒绝。前端没有复制后端审批状态机，只维护 PENDING、SUBMITTING、APPROVED 等 presentation state；HTTP 请求放到后台线程，通过 Qt signal 回 UI thread 更新组件。因为 HTTP command response 和 Runtime stream event 是两个异步通道，我还处理了 race，例如 Runtime 已经 APPROVED 后 late network error 不能把 UI 改成 ERROR，timeout 后 late HTTP success 也不能把 EXPIRED 改成 APPROVED。整个 UI 只消费现有 WP2 public contract，没有修改 Runtime 或泄露 raw Tool 参数。

------

# 33. 2 分钟面试总结

> Phase7 前面已经完成了 Tool Approval Runtime、Streaming/HTTP Transport 和 AgentEvalOps Evaluation，但真实用户仍然需要通过 API 或测试 harness 操作，所以我最后增加了一个 Minimal Approval UI Closure。
>
> UI 直接复用了现有 `/api/chat` 的 `[[ORCH]]` control event。收到 `TOOL_APPROVAL_REQUESTED` 后，ChatPanel 根据 `(run_id, approval_id)` 创建一张 Approval Card，只展示 tool name、risk level 和 risk facts，同时内部保存 invocation binding digest。用户点击 Approve 或 Reject 后，按钮立即进入 SUBMITTING 并禁用，在后台短线程调用已有 HTTP endpoint，结果再通过 Qt signal 回到 UI thread。
>
> 一个关键设计是 UI 不拥有 Runtime truth。点击 Approve 只是用户 intent，不能立即把系统当成 APPROVED；真正状态来自 HTTP domain result 和 `TOOL_APPROVAL_DECIDED` stream event。由于两条通道存在 race，我们定义 terminal presentation state 优先。例如 stream 已经告诉 UI APPROVED，之后即使 HTTP worker 返回 network error，也不能把状态改回 ERROR；如果 Runtime 已经 INVALIDATED_TIMEOUT，late HTTP success 也不能把 EXPIRED 改回 APPROVED。
>
> 生命周期上还处理了 stop、timeout、stream settled 和 chat reset。Pending Card 会按 run_id 清理，Run A 结束不会误伤 Run B；HTTP callback 不持有直接 QWidget 指针，所以 reset 后 late callback 只会 lookup 失败并 no-op。
>
> Final Gate 还发现一个很有价值的问题：为了兼容旧测试 fake，最初 production code 用 `getattr + callable` 把 cleanup 当可选能力，但实际上它属于固定 ChatPanel contract，这样会掩盖 production composition bug。最终恢复显式调用，并让 test fake 补齐 interface。
>
> WP4 最终没有修改 server、Runtime 或 AgentEvalOps，只是把已有 HITL 安全能力补成了一个真正用户可感知和可操作的产品闭环。

------

# 34. WP4 最值得突出三个面试点

### 第一：Presentation State ≠ Runtime Truth

这是架构边界。

------

### 第二：HTTP / Stream Race + Terminal Wins

这是典型异步系统问题。

------

### 第三：Qt Thread Safety + Widget Lifecycle

体现你不是只把按钮“连到 API”就结束，而是考虑：

```text
event loop
thread affinity
late callback
lifecycle cleanup
```

------

# 35. Phase7 现在的最终用户路径

加上 WP4 后，整个 Phase7 可以真正讲成：

```text
High-risk Tool
        ↓
ToolGovernance
        ↓
APPROVAL_REQUIRED
        ↓
WAITING_FOR_APPROVAL
        ↓
Journal-first event
        ↓
Desktop Approval Card
        ↓
Human Approve / Reject
        ↓
HTTP command
        ↓
Runtime CAS
        ↓
APPROVE → execution claim → Tool once
REJECT  → zero Tool execution
        ↓
stream lifecycle feedback
        ↓
UI final state
        ↓
Journal safe evidence
        ↓
AgentEvalOps
        ↓
PASS / FAIL / BLOCKED
```

这比 WP3 收口时的叙事又完整了一层：现在已经真正覆盖 **Runtime → Human → Runtime → Evaluation**。

------

# 36. 推荐 WP4 学习文档名

推荐：

```text
docs/interview/stage5_phase7_wp4_minimal_approval_ui_closure.md
```

如果之后要更新整个 Phase7 总文档，我建议最终总文件仍然使用：

```text
docs/interview/stage5_phase7_tool_approval_hitl.md
```

但将 Scope 更新成：

```text
Minimum Credible Tool Approval HITL
+ Human-facing UI Closure
```

而不是另外制造一个“Phase7 v2”。

WP4 学习节点到这里正式完成。