# Stage7 — Distributed Agent Harness & AI Backend Hardening

## 一、Stage7 到底解决了什么问题

Stage7 的目标不是继续往 Agent 上堆功能，而是解决：

> **当 Agent Runtime 从单进程 Demo 演进到多实例、长任务、外部模型、外部 Tool、MCP、审批、评测之后，如何让 Ownership、Persistence、Cancellation、Side Effect 和 Recovery 仍然保持一致。**

Stage7 最终覆盖：

```text
WP1 — Durable Multi-instance Run Control Plane
WP2 — Durable HITL & Approval Recovery
WP3 — Authenticated Cross-repo Evaluation Candidate Gate
WP4 — Real Provider Streaming / Deadline / Cancellation
WP5 — Tool Side-effect Idempotency & Reconciliation
WP6 — MCP Resilient Session Lifecycle
WP7 — Canonical Path Consolidation & Legacy Compatibility Cleanup
```

Stage7 Final Gate 后又执行了 WP7，因此当前最新 Production Boundary 是：

```text
唯一 Coordinated Runtime
+
Required Durable Services
+
Async Provider Transport
+
Durable Tool Side-effect Ledger
+
Resilient MCP Lifecycle
+
Authenticated Evaluation Target
```

历史 Legacy Runtime、旧 fallback、旧 API、旧 Runtime SQLite authority 和保护它们的测试已经退出当前 Production Boundary。

------

# 二、Stage7 最终状态

最终 Stage7 Final Gate：

```ini
STAGE7_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

P0_COUNT = 0
BLOCKING_P1_COUNT = 0
ACCEPTED_P1_COUNT = 0
P2_COUNT = 2

ARCHITECTURE_REOPEN_REQUIRED = NO
```

随后 WP7：

```ini
WP7_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

STAGE7_CANONICAL_PATH_CONSOLIDATED = PASS

FORWARD_COMPATIBILITY_WITH_LEGACY = NOT_REQUIRED
LEGACY_COMPATIBILITY_REQUIRED = NO
```

因此当前 Stage7 可以认为：

> **功能闭环已经完成，同时历史兼容形成的第二条 Production Path 也已经清理。**

------

# 三、Stage7 最核心的一张图

整个 Stage7 可以压缩成下面这条主线：

```text
User Request
    ↓
Durable Run Control
    ↓
Current Executor + Lease + Fencing
    ↓
Model / Tool Decision
    ↓
Governance
    ↓
Approval
    ↓
Execution Claim
    ↓
Tool Invocation
    ↓
Durable Side-effect State
    ↓
Provider / MCP
    ↓
COMMITTED / UNKNOWN
    ↓
Reconciliation
    ↓
Journal Terminal Truth
```

旁边还有两条重要链：

```text
Model Provider
→ Streaming
→ Deadline
→ Cancellation
→ Output Barrier
```

以及：

```text
AgentEvalOps
→ Authenticated LocalAgent Execution
→ Persisted Evaluation
→ Regression
→ ReleaseDecision
```

Stage7 的本质不是单个组件，而是：

> **这些链路组合以后仍然只有一个 Owner、一个 Truth 和一个 Recovery Contract。**

------

# 四、Stage7 最重要的设计思想：Truth 要拆开

Stage7 最值得记住的是：

> **不同问题必须由不同 Truth 表示，不能拿一个状态字段解释整个系统。**

最终实际拆成：

```text
Run ownership / lease / cancel
→ PostgreSQL Run Control

Run terminal
→ Journal

Approval authorization
→ runtime_tool_approvals

Execution permission
→ runtime_tool_execution_claims

External side-effect outcome
→ runtime_tool_invocations

MCP session availability
→ McpIntegrationComponent

Evaluation result / regression / release
→ AgentEvalOps
```

所以一定要记住：

```text
APPROVED
!=
CLAIMED
!=
COMMITTED
```

同时：

```text
Run CANCELLED
!=
External Tool NOT_COMMITTED
```

以及：

```text
MCP AVAILABLE
!=
Old Side-effect Outcome Known
```

------

# 五、WP1 — Durable Multi-instance Run Control Plane

## WP1 解决的问题

单进程里：

```text
dict[run_id] = running_task
```

还能工作。

一旦多实例：

```text
Instance A
Instance B
```

就会出现：

```text
谁在执行？
谁可以 Cancel？
谁能 Finalize？
A 挂了 B 能不能接管？
旧 A 恢复后还能不能继续写？
```

所以 WP1 把 Run Control 放进 PostgreSQL。

核心能力：

```text
Lease
Owner ID
Fencing Token
Durable Commands
Takeover
Heartbeat / Renew
Cross-instance Cancel
```

Stage7 Final Gate 重新确认 Run control 的 Owner 是 `DurableRunControlService`，PostgreSQL 持有 lease/fence/command，Journal 仍然持有 terminal truth。

------

# 六、Lease 和 Fencing 分别解决什么

Lease 解决：

> 谁现在被允许执行？

例如：

```text
owner=A
lease_until=T
```

Fencing Token 解决：

> 旧 Owner 恢复以后，怎么阻止它继续写？

例如：

```text
A token=10

lease expires

B takeover
token=11
```

以后所有权威 mutation 都必须验证：

```text
token == 11
```

A 即使恢复：

```text
token=10
```

也不能继续：

```text
Finalize
Tool execution
Side-effect state mutation
```

所以：

> **Lease 管当前资格，Fencing 管旧 Executor 的失效。**

------

# 七、为什么只做 Lease 不够

典型问题：

```text
A 拿 lease
↓
网络卡顿

lease expires

B takeover

A 网络恢复
```

如果系统只看：

```text
“我之前拿过 lease”
```

A 仍可能继续写。

Fencing Token 提供的是：

```text
Monotonic Epoch
```

新 Owner 永远拥有更大的 Token。

这也是分布式系统里常见的：

> **Stale Worker Protection。**

------

# 八、WP2 — Durable HITL & Approval Recovery

WP2 解决：

> Approval 不能只存在当前进程内存里。

否则：

```text
Instance A 等 Approval
User 的 approve HTTP 打到 Instance B
```

B 如果只看本地 waiter：

```text
找不到 approval
```

就会失败。

所以审批 Truth 被放入 PostgreSQL。

核心链：

```text
Tool requires approval
→ durable PENDING
→ HTTP APPROVE / REJECT
→ PostgreSQL first-wins
→ current Run worker polling
→ Execution Claim
```

Stage7 Final Gate 重新确认了：

```text
Durable PENDING
Cross-instance decision
Exact binding
Current Fence
Single Claim
```

仍然成立。

------

# 九、Approval 和 Claim 为什么分开

审批：

```text
APPROVED
```

表示：

> 人类允许做这件事。

Execution Claim：

```text
CLAIMED
```

表示：

> 当前这个 Executor 获得一次执行权限。

二者不能合并，因为：

```text
APPROVED
```

之后可能：

```text
Executor A crash
Executor B takeover
```

所以还需要：

```text
current fence
+
single execution claim
```

------

# 十、WP1 + WP2 的组合关系

跨实例审批完整链：

```text
Instance A owns Run
↓
Tool requires approval
↓
PostgreSQL PENDING

HTTP request arrives on Instance B
↓
PostgreSQL APPROVED

Instance A polls durable truth
↓
obtains execution claim
↓
continues
```

因此：

```text
local waiter miss
!=
approval lost
```

------

# 十一、WP3 — Authenticated Cross-repo Evaluation Candidate Gate

WP3 解决：

> AgentEvalOps 如何真实调用 LocalAgent Production Runtime 做发布前评测，同时不获得过大的 Runtime 权限。

之前 Evaluation 如果只是：

```text
直接 import Runtime
Mock Runtime
Synthetic Result
```

并不能证明真实 Production 行为。

WP3 建立：

```text
AgentEvalOps
→ SERVICE JWT
→ LocalAgent FastAPI
→ Production Lifespan
→ Coordinated Runtime
→ Artifact / Final Answer
→ AgentEvalOps Evaluation
→ Regression
→ ReleaseDecision
```

------

# 十二、为什么要 SERVICE Principal

Evaluation 不是普通 Human User。

所以创建：

```text
SERVICE principal
```

并给它窄 Scope：

```text
localagent:evaluation:execute
```

而不是：

```text
ADMIN
```

默认全权限。

核心原则：

> **Machine Identity 也要 Least Privilege。**

------

# 十三、Authentication 和 Authorization 区别

Authentication：

> 你是谁？

比如：

```text
JWT signature
subject
principal
```

Authorization：

> 你可以干什么？

比如：

```text
scope
ownership
endpoint policy
```

WP3 的重要边界：

```text
missing Bearer → 401

authenticated but missing scope → 403
```

------

# 十四、为什么 Scope 和 Ownership 还要分开

有：

```text
localagent:evaluation:execute
```

只表示：

> 可以执行 Evaluation。

不代表：

> 可以 Cancel 所有人的 Run。

所以还有：

```text
owner-bound cancel
```

这两个维度是：

```text
Capability
+
Resource Ownership
```

Stage7 Final Gate 还发现并修了：

```text
SERVICE + ADMIN
```

可能绕过 foreign-run ownership 的风险。

------

# 十五、Runtime Truth 和 Evaluation Authority 怎么分

LocalAgent 持有：

```text
Runtime Truth
Agent execution
terminal outcome
artifact
final answer
provenance
```

AgentEvalOps 持有：

```text
Dataset
Ground Truth
Attempt
Result
Evaluator
Baseline
Candidate
RegressionReport
ReleaseDecision
```

所以：

> LocalAgent 不决定“这个 Candidate 能不能发布”。

而：

> AgentEvalOps 不决定“这个 Run 实际是否执行成功”。

------

# 十六、为什么 Known-bad Candidate 不能改 Ground Truth

错误方式：

```text
Candidate output 没变
Expected output 改错
→ FAIL
```

这是假 Regression。

正确方式：

```text
Same Dataset
Same Ground Truth
Same Evaluator
Same Runtime conditions

Candidate 实际输出退化
→ FAIL
```

这样 Regression 才有意义。

------

# 十七、WP4 — Real Provider Streaming / Deadline / Cancellation

WP4 解决的是：

> 真正外部 LLM Streaming 以后，Timeout、Cancel、Retry 和 Partial Output 怎么保持一致。

核心 Production 链：

```text
ModelInvocationRouter
→ RemoteLLMEngine
→ httpx.AsyncClient
→ SSE
→ Provider-neutral Delta
→ Runtime OutputGate
→ EventChannel
```

Stage7 Final Gate 确认：

```text
AsyncClient
Native SSE
Typed Delta
Absolute Deadline
Cancellation
Output Barrier
Pre-output retry/fallback
Post-output fail-stop
```

仍然成立。

------

# 十八、Provider Streaming != Runtime Streaming

Provider 收到 Token：

```text
Provider Delta
```

不代表用户已经看到。

中间还有：

```text
Parser
Normalization
OutputGate
Journal
EventChannel
```

所以 Runtime 必须定义：

```text
output_started
```

的真正边界。

------

# 十九、Output-started Barrier 为什么放 Runtime Acceptance

错误：

```text
Provider 收到第一个 Token
→ output_started=true
```

但这个 Token 可能还没被 Runtime 接受。

正确：

```text
Runtime successful acceptance / publication
→ output_started=true
```

只有越过这个边界以后：

```text
Retry
Fallback
```

才必须禁止。

------

# 二十、为什么输出后不能 Fallback

例如：

```text
Provider A:
“北京今天...”

然后断线

Provider B:
“根据您的问题...”
```

如果把两个回答拼起来：

```text
一个用户 Response
来自两个 Provider
```

语义已经破坏。

因此：

```text
before output
→ retry/fallback allowed

after output
→ fail-stop
```

------

# 二十一、Deadline 为什么用 Absolute Monotonic Deadline

如果每层都是：

```text
timeout=30s
```

那：

```text
Run 30s
Provider 30s
Tool 30s
MCP 30s
```

可能远远超过 Run Budget。

所以最高层：

```text
absolute monotonic deadline
```

底层只计算：

```text
remaining = deadline - now
```

然后：

```text
effective_timeout = min(remaining, local_cap)
```

Stage7 最终 Deadline 同时约束 Model、Tool、MCP 和 Replay Wait。

------

# 二十二、Cancellation 能保证什么

可以保证：

```text
停止本地等待
停止继续发布输出
关闭本地 HTTP response
best-effort通知 Provider
```

不能保证：

```text
远端 GPU 已停止
远端计费已停止
外部 Tool 未执行
```

所以：

> **Local Cancellation != Remote Abort Proof。**

------

# 二十三、WP5 — Tool Side-effect Idempotency & Reconciliation

WP5 解决：

> Tool 已经可能修改外部世界，但本地不知道是否成功怎么办？

比如：

```text
Create Order
→ Provider committed
→ Response lost
```

本地看到：

```text
Timeout
```

不能：

```text
FAILED
→ retry
```

必须：

```text
UNKNOWN
```

------

# 二十四、WP5 状态机

核心：

```text
PREPARED
    ↓
STARTED
   ├──→ COMMITTED
   └──→ UNKNOWN
             ├──→ COMMITTED
             └──→ NOT_COMMITTED
```

Stage7 Final Gate 确认真实 PostgreSQL：

```text
PREPARED
STARTED
COMMITTED
UNKNOWN
Fencing
CAS
Reconciliation
```

仍然成立。

------

# 二十五、为什么 STARTED 要在 Provider Call 前写

正确：

```text
STARTED committed locally
↓
Provider call
```

错误：

```text
Provider call
↓
STARTED
```

如果中间 Crash：

```text
Provider 可能执行
Local 仍 PREPARED
```

恢复后可能再次执行。

------

# 二十六、为什么 UNKNOWN 是一等状态

传统：

```text
SUCCESS
FAILED
```

不够表达跨系统事实。

Timeout 只说明：

> 我没有拿到可信结果。

不说明：

> Provider 没执行。

所以：

```text
UNKNOWN != FAILED
UNKNOWN != NOT_COMMITTED
```

这是 Stage7 里非常重要的面试点。

------

# 二十七、为什么 UNKNOWN 不能 Generic Retry

因为：

```text
第一次已经成功
response lost
UNKNOWN
```

如果直接重试：

```text
第二次 side effect
```

可能重复执行。

所以：

```text
UNKNOWN
→ no generic retry
→ reconciliation
```

------

# 二十八、Reconciliation 是什么

通过：

```text
provider_operation_id
stable idempotency key
status API
```

查询 Provider 实际状态。

Provider Adapter 只负责：

```text
query
+
normalize
```

输出：

```text
COMMITTED
NOT_COMMITTED
STILL_PENDING
UNKNOWN
```

真正修改 Local Durable State：

```text
DurableToolInvocationService
```

------

# 二十九、为什么不宣称 Exactly-once

LocalAgent 可以保证：

```text
durable intent
single active fenced executor
explicit UNKNOWN
provider-specific reconciliation
```

但如果第三方 Provider：

```text
不支持 idempotency
不支持 operation query
```

LocalAgent 无法凭空提供：

```text
generic external exactly-once
```

所以正确说法：

> 我们控制重复副作用风险，但不承诺通用跨系统 Exactly-once。

------

# 三十、WP2 + WP5 的组合关系

```text
APPROVED
↓
Execution Claim
↓
PREPARED
↓
STARTED
↓
Provider
↓
COMMITTED / UNKNOWN
```

所以：

```text
Approval
```

负责：

> 可不可以做？

```text
Execution Claim
```

负责：

> 谁能做一次？

```text
WP5 ledger
```

负责：

> 外部到底发生了什么？

------

# 三十一、WP1 + WP5 的组合关系

如果：

```text
A token=10 STARTED

B takeover token=11
```

旧 A 不能：

```text
COMMIT
mark UNKNOWN
reconcile
```

只有当前 fencing token 可以修改 Durable Side-effect State。

这保证了：

```text
Tool Idempotency
```

不会被 Stale Executor 绕过。

------

# 三十二、WP6 — MCP Resilient Session Lifecycle

WP6 解决：

> MCP Server 挂了以后如何安全重连？

不是简单：

```text
restart
→ continue
```

而是：

```text
restart
→ initialize
→ identity check
→ tools/list
→ Tool identity check
→ schema digest check
→ generation publish
```

------

# 三十三、MCP Lifecycle

```text
STARTING
→ AVAILABLE
→ DEGRADED
→ RECONNECTING
→ AVAILABLE
```

或者最终：

```text
CLOSED
```

`McpIntegrationComponent` 是唯一 Lifecycle / Reconnect Owner。

------

# 三十四、为什么要 Session Generation

例如：

```text
generation=4
server dies
generation=5
```

旧 Invocation 必须仍绑定：

```text
generation=4
```

不能偷偷：

```text
旧 handle
→ 换成 generation=5 client
```

否则无法判断某次 Attempt 到底发生在哪个 Session。

------

# 三十五、Reconnect 为什么是重新建立信任

新的 Server 可能：

```text
name changed
Tool missing
Schema changed
```

所以：

> Transport 恢复并不代表 Runtime Contract 仍然成立。

WP6 会验证：

```text
configured server_id
remote serverInfo.name
Frozen Tool Identity
Canonical Schema Digest
```

------

# 三十六、为什么 Extra Tool 不自动注册

Reconnect 后如果 MCP Server 新增：

```text
delete_everything
```

LocalAgent 不应该：

```text
ToolRegistry.register()
```

否则远端 Server 就可以动态修改 Runtime Safety Surface。

所以：

```text
Extra Tool
→ ignore
```

------

# 三十七、为什么 Read-only Replay 可以做

只有 LocalAgent Frozen Spec 判断：

```text
side_effect_kind = NONE
idempotency = READ_ONLY
```

才可以：

```text
Transport failure
→ validated new generation
→ replay once
```

Remote MCP 的：

```text
readOnlyHint=true
```

不能授予权限。

------

# 三十八、为什么 Side-effect MCP 绝不 Replay

```text
generation 4
→ side-effect call
→ server executes
→ connection drops
```

如果 generation 5 重放：

可能执行两次。

所以：

```text
disconnect
→ WP5 UNKNOWN
```

而不是：

```text
reconnect
→ replay
```

------

# 三十九、WP5 + WP6 是 Stage7 最关键的一条组合链

真实验证：

```text
PREPARED
→ STARTED
→ MCP tools/call
→ process disconnect
→ UNKNOWN
```

然后：

```text
MCP reconnect
→ generation+1
```

旧 Invocation：

```text
still UNKNOWN
```

Provider Call Count：

```text
1
```

这说明：

> **Transport Availability 和 Operation Truth 是完全独立的。**

------

# 四十、WP7 — Canonical Path Consolidation

WP1～WP6 把能力补齐以后，WP7 又解决：

> 历史上为了兼容旧版本保留下来的第二条路怎么办？

最终：

```text
Compatibility Debt = 37

Legacy Paths Deleted = 24
Legacy Paths Rewritten = 13
Legacy Test Files Deleted = 19
Legacy Test Nodes Deleted = 116
Canonical Callers Migrated = 53
```

------

# 四十一、WP7 最重要的思想

不是：

```text
全部 Legacy 字样删除
```

而是：

```text
Production Reachability
+
Current Contract
+
Authority
```

决定是否保留。

例如保留：

```text
Model Sync Facade
LegacyStringToolAdapter
Memory SQLite Compatibility
MCP Protocol Compatibility
```

因为它们仍然是 Current Contract。

------

# 四十二、Stage7 最终 Canonical Architecture

当前生产基线：

```text
FastAPI / ChatService
→ CoordinatedRuntimeFactory
→ Durable Run lease / fencing
→ Model / Scheduler
→ ToolRegistry
→ ToolAdapter
→ Typed Validation
→ Governance
→ Durable Approval
→ Execution Claim
→ ToolExecutionService
→ Durable Side-effect Ledger
→ EventChannel
→ PostgreSQL Journal
```

MCP：

```text
McpIntegrationComponent
→ Validated Session Generation
→ Frozen Registry / Governance
→ MCP Adapter
```

Evaluation：

```text
AgentEvalOps
→ Authenticated evaluation-v2
→ LocalAgent Production Runtime
→ Persisted Evaluation
→ ReleaseDecision
```

------

# 四十三、Stage7 工程方法类高频问题

## 1. 为什么把 Run Control 放 PostgreSQL？

因为多实例以后 Process Memory 不能提供共享 Ownership、Lease、Fencing 和 Cross-instance Commands。

------

## 2. 为什么 Journal 不直接当 Run Control？

Journal 适合：

```text
immutable terminal/evidence truth
```

Run Control 需要：

```text
mutable lease
heartbeat
takeover
commands
```

职责不同。

------

## 3. 为什么 Approval 和 Claim 分开？

Approval 是授权。

Claim 是当前 Executor 获得的一次执行许可。

------

## 4. 为什么 Claim 和 Side-effect State 还要分开？

Claim 不证明 Provider 已经成功。

------

## 5. 为什么 Timeout 不应该直接 FAILED？

因为 Timeout 只说明没拿到结果。

跨过 External Boundary 后应该 UNKNOWN。

------

## 6. 为什么 Model Output 后禁止 Fallback？

因为会把两个 Provider 的输出拼进同一个用户响应。

------

## 7. 为什么 MCP Schema 变化不能 Hot Reload？

因为远端 Provider 不应该运行时修改 Local Runtime Safety Contract。

------

## 8. 为什么 Read-only Replay Authority 不能信 MCP annotation？

因为 remote metadata 属于不可信输入。

最终 Risk Authority 在 Local Governance。

------

## 9. 为什么 Evaluation 用独立 SERVICE Principal？

Machine-to-machine 调用也应该做最小权限隔离。

------

## 10. 为什么最后还要做 WP7？

因为默认走新链路不等于旧链路不存在。

只有清掉旧 Production Reachable Path，Authority 才真正唯一。

------

# 四十四、30 秒 Stage7 总结

Stage7 我主要把 Agent Runtime 从单进程执行补成了一个可跨实例协调的执行闭环。

Run 层用 PostgreSQL Lease 和 Fencing 管理 Ownership；审批和 Tool Execution Claim 做了持久化；外部 Tool 副作用用 PREPARED、STARTED、UNKNOWN 和 Reconciliation 避免结果不确定时盲目重试。

模型调用改成 Async SSE，并统一受 Run Deadline、Cancellation 和 Output Barrier 约束。MCP 则增加了 Session Generation、Identity/Schema Revalidation 和安全 Reconnect，Read-only 最多重放一次，Side-effect 绝不自动 Replay。

最后又清掉了历史 Legacy Runtime、Fallback、旧 API 和旧 Tests，让 Production 只剩一条 Canonical Path。

------

# 四十五、2 分钟 Stage7 总结

Stage7 的重点是 Agent Runtime 的生产化一致性。

首先 Run Control 从 Process Memory 移到了 PostgreSQL。每个 Run 只有一个有效 Executor，通过 Lease 和递增 Fencing Token 控制 Takeover，旧 Executor 即使恢复也不能继续写 Terminal 或执行 Tool。

在这个基础上 HITL Approval 也做成 Durable。Approval、Execution Claim 和 External Tool Outcome 分成三个 Truth，避免“审批通过”等同于“已经执行成功”。

模型调用方面，我把 Remote Provider 收敛到 application-scoped Async HTTP 和 Native SSE，RunContext 持有 Absolute Deadline，Provider、Tool、MCP 都只能消费 Remaining Budget；Retry/Fallback 只允许发生在 Runtime 接受第一段输出之前。

Tool Side-effect 是另外一个重点。外部调用只要已经可能发生，但本地拿不到可靠结果，就进入 UNKNOWN，不会标成 FAILED 自动重试。之后只有 Provider-specific Reconciliation 能把 UNKNOWN 收口到 COMMITTED 或 NOT_COMMITTED，所以我们没有宣称 generic exactly-once。

MCP 这边增加了 Resilient Session Lifecycle。Reconnect 后必须重新验证 Server Identity、Frozen Tool Identity 和 Schema Digest，成功才发布新的 Session Generation。Read-only Tool 最多跨 generation Replay 一次，Side-effect Tool 断线后直接进入 WP5 UNKNOWN。

最后我又清理了一轮 Legacy Compatibility Debt，把旧 Runtime、Optional fallback、SQLite Runtime authority、旧 Evaluation API 和只保护旧 Contract 的测试都移除了，最终 Production 只保留一条 Canonical Path。

------

# 四十六、5 分钟面试主线怎么讲

建议按这个顺序讲。

## 第一段：为什么做 Stage7

> 项目早期单进程 Runtime 已经能跑 Agent、Tool、RAG 和 HITL，但如果开始考虑多实例、进程重启、外部 Provider 和 MCP，原来很多 Process-local 假设就不成立了，所以 Stage7 主要解决 Runtime 的 Ownership 和 Failure Semantics。

## 第二段：Run + HITL

> 我先把 Run Ownership 做成 PostgreSQL Lease + Fencing，然后把 Approval 和 Execution Claim 也持久化，这样 HTTP 请求打到任何实例都不会丢审批状态。

## 第三段：Provider

> 模型调用改成 Async SSE，并把 Absolute Deadline 和 Cancellation 往下传，Retry/Fallback 只允许在用户还没看到输出之前。

## 第四段：Side Effect

> Tool 副作用不能把 Timeout 当 Failed，所以加了 PREPARED、STARTED、UNKNOWN 和 Reconciliation。这里不宣称 Exactly-once，而是明确暴露不确定性。

## 第五段：MCP

> MCP Server 断线后不是简单重启，而是新 Session 必须重新验证 Identity、Tool 和 Schema。Read-only 可以最多 Replay 一次，Side-effect 不能 Replay。

## 第六段：Evaluation + Cleanup

> AgentEvalOps 使用窄权限 SERVICE JWT 调真实 LocalAgent Runtime 做 Candidate Gate。最后还清理了历史 Compatibility Debt，让这些 Authority 不再有旧路径可以绕过去。

------

# 四十七、Stage7 高频追问

## Fencing Token 是干什么的？

防止 Lease 已失效的旧 Executor 恢复以后继续修改共享状态。

------

## Approval exactly-once 是怎么来的？

严格说 Approval 是 first-wins durable decision；Execution Claim 提供单次执行授权，而不是对外部 Side-effect 宣称 exactly-once。

------

## Tool Timeout 怎么处理？

如果还没跨 Side-effect Boundary，可以普通失败。

如果已经可能调用 Provider：

```text
UNKNOWN
```

------

## UNKNOWN 后什么时候能 Retry？

不能 Generic Retry。

只有 Provider Reconciliation 明确得到：

```text
NOT_COMMITTED
```

之后，才由具体 Tool Policy 决定未来是否重新执行。

------

## MCP Server 重连以后为什么不能恢复旧 Side-effect 调用？

因为重连只能证明 Transport 恢复，不能证明旧操作未发生。

------

## Model Provider 为什么要 application-scoped AsyncClient？

连接池复用、生命周期统一、Shutdown 可控，同时避免每次 Invocation 新建连接。

------

## 为什么不直接相信 MCP `readOnlyHint`？

因为 Risk Classification Authority 必须在 LocalAgent，不能交给不可信 Provider。

------

## Evaluation 为什么不是 LocalAgent 自己决定 PASS/FAIL？

因为 Runtime Execution Truth 和 Evaluation Authority 是两个不同 Domain。

------

## 为什么删旧测试？

因为它们保护的是已经废弃的 Contract，而不是 Current Production Contract。

------

# 四十八、Stage7 Bad Cases

## Bad Case 1

```text
RunRegistry cache miss
→ assume Run inactive
```

错误。

跨实例 Truth 在 PostgreSQL。

------

## Bad Case 2

```text
APPROVED
→ execute directly
```

错误。

还需要 Current Fence + Execution Claim。

------

## Bad Case 3

```text
Tool timeout
→ FAILED
→ retry
```

Side-effect 可能已经发生。

------

## Bad Case 4

```text
Provider first token
→ output_started
```

真正边界应该是 Runtime acceptance。

------

## Bad Case 5

```text
mid-stream error
→ fallback another provider
```

会污染用户可见 Response。

------

## Bad Case 6

```text
MCP reconnect success
→ replay previous side-effect
```

可能重复执行。

------

## Bad Case 7

```text
remote MCP readOnlyHint=true
→ auto replay
```

Remote metadata 不应该拥有 Governance Authority。

------

## Bad Case 8

```text
Evaluation SERVICE
→ ADMIN bypass
```

Machine Principal 应使用 Narrow Scope。

------

## Bad Case 9

```text
new Runtime works
→ old Runtime 留着兼容测试
```

旧路径可能重新形成 Production Bypass。

------

# 四十九、Stage7 最值得记住的 10 句话

1. **Lease 决定当前谁能执行，Fencing Token 阻止旧 Executor 复活。**
2. **Local Cache 可以加速，但不能成为跨实例 Truth。**
3. **APPROVED != CLAIMED != COMMITTED。**
4. **Timeout 表示结果未知，不等于操作失败。**
5. **UNKNOWN 必须是一等状态，而不是异常字符串。**
6. **Retry Authority 必须有明确边界，不能每层自己重试。**
7. **Runtime 接受第一段输出以后，Model Fallback 必须停止。**
8. **MCP Reconnect 是重新建立信任，不只是重新建立连接。**
9. **Transport Recovery 不能改变旧 Side-effect Outcome。**
10. **Canonical Architecture 只有在 Legacy Bypass 真正退出 Production 后才算成立。**

------

# 五十、Stage7 当前真实完成边界

## 已完成

```text
Durable Multi-instance Run Control

Lease / Fencing / Takeover

Cross-instance Cancel

Durable HITL

Durable Execution Claim

Authenticated Evaluation Service Principal

Cross-repo Candidate Gate

Async Remote Provider

Native SSE

Provider-neutral Delta

Absolute Deadline

Cancellation Propagation

Output-started Barrier

Pre-output Retry/Fallback

Post-output Fail-stop

Durable Tool Side-effect Ledger

PREPARED / STARTED / COMMITTED / UNKNOWN

Provider-specific Reconciliation

MCP Session Lifecycle

Generation Isolation

Identity / Schema Revalidation

Read-only Max-one Replay

Side-effect No Replay

Legacy Compatibility Cleanup

Single Canonical Production Path
```

------

# 五十一、Stage7 当前没有完成什么

不要在面试里扩大。

未完成：

```text
Generic External Exactly-once

Saga

Compensation Engine

2PC

MCP HTTP / Streamable HTTP

Dynamic MCP Tool Hot Reload

Multi-provider MCP HA

Resumable Model Streaming

Remote Provider Cancel Guarantee

Online Evaluation Service Token Refresh

Real DeepSeek in ordinary CI

Large LLM Judge in ordinary CI
```

这些都属于当前明确 Capability Boundary。

------

# 五十二、当前两个 P2

目前仍有两个非阻断 P2：

```text
1. Native-tool initial-selection buffering

2. AgentEvalOps workflow checkout floating LocalAgent main
```

前者是 Tool-call 安全与 Streaming 体验之间的取舍。

后者是 CI Reproducibility / Dependency Pinning 的 Production Awareness 问题。

都不影响 Stage7 核心 Owner 和 Safety Correctness。

------

# 五十三、Truth / Completion Boundary

Stage7 最准确的 Completion Statement：

> 当前 LocalAgent 已形成单一 Coordinated Runtime Production Path。Run Ownership、Approval、Execution Claim 和 External Side-effect Outcome 分别由明确 Durable Authority 持有；Model Invocation、Tool Runtime 和 MCP Lifecycle 共享统一 Deadline / Cancellation / Governance 边界；External Side-effect 不确定性通过 UNKNOWN 和 Provider-specific Reconciliation 显式处理；AgentEvalOps 通过窄权限 SERVICE Principal 调用真实 LocalAgent Runtime 形成 Candidate Gate；历史 Legacy Runtime、Fallback、旧 Persistence Authority 和旧 Evaluation Contract 已从 Production Boundary 清除。

------

# 五十四、最终一句话总结

> **Stage7 的核心不是“做了多实例、Streaming、MCP 和评测”，而是把 Agent 在分布式执行过程中最容易混在一起的 Ownership、Authorization、Execution Permission、External Outcome、Transport Availability 和 Evaluation Authority 全部分开，并让每一种 Truth 都只有一个明确 Owner。**