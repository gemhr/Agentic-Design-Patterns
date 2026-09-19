# Stage8-WP3 — Async Execution & Failure Triage Closed Loop

## 1. 名词 / 概念速览

**异步外部执行（Asynchronous External Execution）**
Agent 只负责启动远程任务并获得 execution_id，不在当前 Run 中持续等待任务完成。

**外部执行任务（ExternalExecutionJob）**
Stage8 持久化的业务对象，用于跟踪某次远程测试任务，而不是替代 Runtime Run。

**结果摄入（Result Ingestion）**
外部 Executor 通过 callback 把执行结果写回 Stage8 的过程。

**终态首次生效（Terminal First-wins）**
SUCCEEDED / FAILED / UNKNOWN / CANCELLED 等终态一旦首次提交，后续冲突终态不能覆盖它。

**失败归因（Failure Triage）**
基于 Case、环境、日志、执行结果、Feature 等证据，对失败原因进行分类和解释。

**失败证据包（FailureEvidencePackage）**
Failure Triage 的权威输入集合，包含 execution、result、case、environment、executor、log、feature、TestPlan 等信息。

**业务重跑（Business Rerun）**
一次新的测试执行尝试，与底层 Tool Retry 不是同一个概念。

**工具未知状态（Tool UNKNOWN）**
无法确认某个副作用 Tool 是否已真正提交，例如请求超时但外部可能已执行。

**外部任务未知状态（External Job UNKNOWN）**
Stage8 当前无法确认远程测试任务状态，与 Tool UNKNOWN 属于不同 Domain。

**持久化审批（Durable Approval）**
`create_ticket` 等高风险 Tool 的审批事实写入数据库，Agent Run 不需要等待人工审批。

**程序化工具调用（Programmatic Tool Invocation）**
Application Service 不是靠模型主动选择 Tool，而是主动触发 Tool，但仍必须进入现有 Tool Runtime。

------

# 2. 本 WP 解决了什么业务问题

前两个 WP 已经完成：

```text
Feature
→ Risk
→ TestPlan
→ Human Review
→ External Platform Tool
```

但真实测试工程还有一个非常关键的问题：

> 远程测试可能跑几个小时，Agent 怎么等？

错误路线是：

```text
Agent Run
→ start_execution
→ poll status
→ sleep
→ poll status
→ ...
→ 几小时后完成
```

这样会让一次 Agent Run：

- 长时间占用 Runtime；
- Deadline 语义失效；
- Budget 难以控制；
- Recovery 复杂；
- 人工审批 / 远程系统生命周期和模型生命周期混在一起。

WP3 最终采用：

```text
Agent Run
→ start_execution
→ execution_id
→ Agent Run terminal

ExternalExecutionJob
→ RUNNING

几小时后 callback
→ ExecutionResult
→ 新的 Failure Triage Run
```

因此：

```text
Mission = 长生命周期业务流程
Run = 一次短生命周期智能计算
ExternalExecutionJob = 外部测试任务生命周期
```

三个 Owner 被明确分开。Final Gate 已确认 `start_execution` 只等待短时 Tool 提交并返回 execution_id，不轮询外部终态。

------

# 3. 工程构建方法问答

## 为什么不能让 Agent Run 一直等远程测试？

因为 Run 的本质是：

```text
bounded execution
```

它通常有：

```text
deadline
budget
cancellation
terminal state
```

而远程测试属于：

```text
business process
```

可能持续几小时。

所以：

> 外部任务应该 outlive 当前 Agent Run，而不是反过来让 Run 承担业务等待。

------

## Mission、Run、ExternalExecutionJob 三者是什么关系？

可以理解成：

```text
FeatureTestMission
│
├─ Risk Analysis Run
├─ Test Planning Run
├─ ExternalExecutionJob
└─ Failure Triage Run
```

Mission 是最高层业务生命周期。

Run 负责智能计算。

ExternalExecutionJob 负责外部测试执行事实。

三者不能互相替代。

------

## 为什么 ExternalExecutionJob 要落 PostgreSQL？

因为远程任务可能：

- 几小时后才返回；
- 服务中途重启；
- callback 重复；
- 用户重新打开页面；
- Triage 后续还要引用。

所以：

```text
execution_id
mission_id
status
result
version
```

必须是 durable state，而不是内存变量。

WP3 最终由 `Stage8ExecutionService + stage8_external_execution_jobs` 持有这部分业务 Authority。

------

## 为什么启动外部执行前要先持久化 PENDING Job？

这是一个很重要的一致性问题。

错误顺序：

```text
先调用 external start
→ EXEC-001 已启动

然后 insert Job
→ DB 失败
```

最终：

```text
外部任务正在跑
但 Stage8 完全不知道它存在
```

Sol 最后调整为：

```text
persist PENDING Job
+
Mission CAS → EXECUTING
→ external mutation
```

这样即使后续失败，至少数据库里还留有一个可 reconciliation 的 Job。

------

## 这样是否已经完全解决跨系统一致性？

没有。

当前仍存在一个明确 Completion Boundary：

```text
external start succeeds
→ execution_id 回填 DB 失败
```

此时 PENDING Job 会保留，但还没有自动 reconciliation。

Final Gate 把这件事明确列为 Accepted Limitation。

面试不要说：

> 外部执行和数据库完全原子。

应该说：

> 我们通过先持久化 PENDING Job 缩小 failure window，但外部系统和本地 PostgreSQL 之间不存在分布式事务，目前保留 reconciliation 缺口。

------

## 为什么 callback 不走 Tool Runtime？

因为 callback 是：

```text
External System
→ informs us of a fact
```

它不是：

```text
Agent
→ asks external system to perform an action
```

因此：

```text
callback
→ typed API
→ Stage8ExecutionService
→ persistence
```

而不是：

```text
callback
→ ToolInvocation
```

Tool Runtime 管的是主动外部操作。

Callback 属于 External Fact Ingestion。

------

## callback 为什么不能相信 caller 传 mission_id？

因为 callback 的 Authority 是：

```text
execution_id
```

正确路径：

```text
execution_id
→ durable ExternalExecutionJob
→ mission_id
```

而不是：

```text
caller says mission_id=MISSION-B
```

然后系统直接更新 MISSION-B。

最终实现中 Mission binding 完全从 durable Job 反查，callback 不接受 caller mission authority。

------

## 为什么 callback 要 first-wins？

假设网络或 Executor 有重复回调：

```text
Callback A = FAILED
Callback B = SUCCEEDED
```

如果简单：

```sql
UPDATE job SET status = ?
```

后来的结果就会覆盖前面的终态。

这会导致：

```text
先触发了 PRODUCT Triage
后来又变成 SUCCEEDED
```

整个业务状态失真。

所以 WP3 使用：

```text
PostgreSQL row lock
+
immutable terminal
+
version increment
```

只有第一条终态写入成功。

------

## 重复 FAILED 为什么尤其危险？

因为 Failure Triage 后可能：

```text
PRODUCT
→ create_ticket
```

而 WP2 已经明确：

```text
create_ticket = NON_IDEMPOTENT
```

如果重复 FAILED callback 每次都跑一次 Triage：

```text
FAILED callback 1
→ Approval A

FAILED callback 2
→ Approval B
```

用户两次都批准，就可能创建两个 Ticket。

所以 WP3 不只是保证 Job status 幂等，还要保证：

> 只有 terminal transition winner 能触发 downstream Triage。

Final Gate 已确认重复 FAILED 不会新建第二个 approval。

------

## Failure Triage 为什么还要做 Evidence Authority？

因为失败分析比 Risk Analysis 更容易幻觉。

模型可能看到日志后说：

```text
“根据 LOG-999，这是环境故障”
```

但实际根本没有 `LOG-999`。

所以 WP3 延续 WP1：

```text
system
→ builds authoritative evidence map

model
→ returns evidence_ids + interpretation
```

模型不能创造 source identity。

Final Gate 确认 Execution / Result / Case / Environment / Executor / Log / Feature / TestPlan 都由系统构造 Evidence。

------

## 为什么 Failure Triage 独立 API 只接受 execution_id？

Luna 初版允许 caller 自己传 Evidence。

这意味着调用者可以说：

```text
execution_id = EXEC-001
evidence = [我自己构造的任意数据]
```

这样独立 API 和 Workflow 的 Evidence Authority 就不一致。

Sol 最终做了 Breaking Change：

```text
API input = execution_id
```

然后：

```text
Application Service
→ load Job
→ load Mission/TestPlan/Case/Environment/Logs
→ reconstruct FailureEvidencePackage
```

因此独立调用和 Workflow 使用同一 Truth。

------

## Failure Triage 为什么是一个新的 Run？

因为它是一次新的智能推理：

```text
Execution failed
```

发生在初始 Execution Planning Run 已经结束很久之后。

正确：

```text
callback
→ new Failure Triage Run
```

而不是恢复原先那个已经 terminal 的 Agent Run。

------

## Failure Triage 有哪些分类？

当前至少：

```text
PRODUCT
TEST_DATA
ENVIRONMENT
TOOL_CHAIN
INFRASTRUCTURE
UNKNOWN
```

这些分类用来决定后续业务动作。

例如：

```text
PRODUCT
→ TicketDraft

TEST_DATA
→ future CandidateRepair

UNKNOWN
→ human review
```

------

## PRODUCT 为什么先生成 TicketDraft，而不是直接 create_ticket？

因为：

```text
TicketDraft
```

只是 Agent 的业务建议。

而：

```text
create_ticket
```

是外部 Side Effect。

所以正确：

```text
Failure Triage
→ typed TicketDraft
→ governed create_ticket
```

而不是：

```text
Failure Triage Agent
→ TicketPlatform.create()
```

------

## create_ticket 为什么不能让 Triage Run 等人工审批？

因为这会重新犯最开始的问题。

错误：

```text
Triage Run
→ APPROVAL_REQUIRED
→ 等用户 2 小时
→ continue
```

正确：

```text
Triage Run
→ create durable pending approval
→ return
```

之后由用户动作和后续 continuation 处理。

Final Gate 明确：

```text
TRIAGE_RUN_WAITS_FOR_APPROVAL = NO
```

------

## GovernedToolInvoker 是什么？

它是 WP3 新增的 programmatic facade。

业务代码需要主动调用：

```text
start_execution
create_ticket
```

但不能为了程序化调用就：

```text
Application Service
→ adapter.invoke_once()
```

所以增加一个薄 facade。

关键要求是：

> facade 只负责接现有 Tool Runtime，不重新成为 Governance Owner。

Sol 审计发现 Luna 初版确实有“半套 Governance”的问题，后来改为真实复用既有 Authority。

------

## GovernedToolInvoker 复用了哪些 Authority？

最终 Final Gate 记录：

```text
ToolRegistry
authorize/evaluate
ResourceAuthorization
durable Run lease
ToolExecutionService
DurableToolInvocationService
DurableApprovalService
```

也就是：

> Programmatic Tool Invocation 和 Model-selected Tool Invocation 可以入口不同，但 Execution Authority 必须相同。

------

## TestPlan 已经 APPROVED，为什么启动执行还要检查 version/digest？

因为可能出现：

```text
TestPlan v1
→ APPROVED

后来生成 TestPlan v2

系统只查：
“有没有 APPROVED TestPlan Review？”
```

那 v1 的审批可能错误放行 v2。

WP3 最终执行 Gate 精确绑定：

```text
mission_id
subject_id
version
digest
```

旧版本 Review 不能放行当前 TestPlan。

------

## Tool UNKNOWN 为什么不能自动重试 start_execution？

例如：

```text
start_execution
→ Provider 已经启动 EXEC-001
→ network response lost
→ Tool UNKNOWN
```

如果业务层看到 UNKNOWN 后自动：

```text
start_execution again
```

就可能启动第二次。

因此：

```text
Tool UNKNOWN
→ unresolved
→ reconciliation / human handling
```

WP3 明确没有自动 retry。

------

## Tool UNKNOWN 和 Failure Triage UNKNOWN 是一回事吗？

不是。

### Tool UNKNOWN

```text
不知道副作用是否提交
```

例如：

```text
Ticket 到底创建没创建？
Execution 到底启动没启动？
```

### Triage UNKNOWN

```text
知道测试失败了
但不知道失败原因
```

一个是执行状态不确定。

一个是根因分析不确定。

Owner 完全不同。

------

# 4. 30 秒项目回答

> 我们的测试任务可能跑几个小时，所以没有让 Agent Run 一直轮询远程 Executor，而是引入了持久化 ExternalExecutionJob。Agent 只通过已有 Tool Runtime 启动执行，拿到 execution_id 后当前 Run 就结束，Mission 进入 EXECUTING。之后 Executor callback 根据 execution_id 找到 durable Job，用数据库 row lock 做 terminal first-wins。成功就结束 Mission，失败就启动新的 Failure Triage Agent。Triage 的 Evidence 由系统从执行结果、Case、环境、日志和 TestPlan 重建，模型不能自己编证据。PRODUCT Failure 会生成 TicketDraft，再走已有 create_ticket Governance 和 HITL，而且 Triage Run 不等待人工审批。

------

# 5. 2 分钟项目回答

> Stage8 做到远程测试时，最大的设计点是把 Agent Run 和真实测试任务的生命周期拆开。
>
> 真实测试可能跑几个小时，但 AgentCore Run 本身是带 Deadline、Budget 和 Terminal State 的 bounded execution，所以我没有让 Agent Run poll Executor，而是新增了一个 PostgreSQL 持久化的 ExternalExecutionJob。
>
> 执行前先确认当前 TestPlan 的 Business Review 已经批准，而且不是只查一个 APPROVED 状态，而是精确匹配 mission、subject、version 和 digest。然后通过现有 Tool Runtime 调 `stage8_start_execution`，拿到 external execution ID 后 Agent Run 就结束，Mission 转成 EXECUTING。
>
> 外部任务结束以后通过 callback 回来。Callback 不信任 caller 给的 mission_id，而是用 execution_id 反查 durable Job。终态更新使用 PostgreSQL row lock 和 immutable terminal 做 first-wins，所以重复 callback 或 FAILED/SUCCEEDED 冲突不会覆盖已有终态。
>
> 如果执行失败，只有抢到 terminal transition 的那个请求会触发新的 Failure Triage Run。Triage Agent 同样复用现有 Specialist Runner，输出 strict JSON，最多 repair 一次；Evidence Package 由系统从执行结果、Case、Environment、Executor、Logs、Feature 和 TestPlan 重建，模型只能引用真实 Evidence ID。
>
> 如果分类是 PRODUCT，先生成 typed TicketDraft，再调用现有 `stage8_create_ticket`。这个 Tool 是 non-idempotent、高风险，所以仍然走 durable approval 和 execution claim。Triage Run 看到 APPROVAL_REQUIRED 后直接结束，不会等待用户几个小时。
>
> 这个 WP 的核心其实是把 Mission、Agent Run、External Job、Tool Invocation 四种不同生命周期和 Authority 分开，同时把异步 callback、重复回调和后续副作用串成一条真实闭环。

------

# 6. 高频追问 + 简答

## 为什么不用 Kafka？

当前目标是内部业务闭环。

已有 PostgreSQL durable Job + callback 已经足够表达：

```text
start
→ wait externally
→ callback
→ triage
```

如果以后需要大规模异步消费、HA worker、backpressure，再考虑 Kafka。

当前不为了形式增加基础设施。

------

## 为什么不使用 Temporal？

同样因为当前需求还没有复杂到：

```text
大量长期 Workflow
复杂 compensation
大规模 timer
跨服务 durable orchestration
```

Mission + PostgreSQL Job 足够。

------

## callback 重复怎么办？

同一个 terminal callback：

```text
FAILED → FAILED
```

幂等。

冲突 terminal：

```text
FAILED → SUCCEEDED
```

后者不能覆盖前者。

只有第一次 terminal transition winner 能触发 downstream Triage。

------

## 你们实现 exactly-once 了吗？

不能简单说严格 exactly-once。

更准确：

> 我们通过 DB first-wins、Triage claim、Approval binding 和 Execution Claim，避免同一个业务结果重复触发危险副作用。

但跨 PostgreSQL 和外部 Executor 仍然存在 failure window，并没有分布式事务。

------

## Triage claim 是什么？

即使 callback 已经 first-wins，还有可能：

```text
callback processing
independent triage API
```

同时触发 Triage。

所以增加 DB claim，确保同一个失败 Job 的 Triage / Ticket downstream 不被并发执行两次。

Final Gate 明确记录 Product Ticket duplicate prevention 使用了 DB triage claim。

------

## Failure Triage 为什么不用 Memory 做 Evidence？

Memory 是上下文辅助，不是业务 Truth。

Failure Triage 必须引用：

```text
ExecutionResult
Case
Environment
Logs
TestPlan
```

这些 durable / external facts。

Memory 可以以后补充历史经验，但不能决定本次执行到底发生了什么。

------

## 为什么没有 TEST_DATA 自动修复？

因为本 WP 首要目标是闭合 async execution + triage + ticket 路径。

自动修复还涉及：

```text
哪些字段允许改
repair count
新 execution attempt
formal case vs temporary override
```

当前明确作为 Accepted P1 保留。

------

## 如果以后实现自动修复，哪些字段不能自动改？

至少：

```text
Expected Result
Assertion
Threshold
Requirement Mapping
```

这些改变测试判断标准或需求含义，需要 Business Review。

------

## 业务重跑和 Tool Retry 有什么区别？

Tool Retry：

```text
同一个 ToolInvocation
```

因为传输或 Provider 问题重试。

Business Rerun：

```text
上一次测试真的执行结束
→ 根据 Triage 做新的 Execution Attempt
```

它是新的业务操作，有新的 execution_id。

两者 Authority 不能混。

------

## Failure Triage API 为什么不是直接传整个 EvidencePackage？

因为那会让 caller 成为 Evidence Authority。

现在只传：

```text
execution_id
```

由服务端重建整个 EvidencePackage，更安全也更一致。

------

## start_execution 成功但 DB 更新失败怎么办？

当前会保留提前创建的 PENDING Job。

但自动 reconciliation 尚未实现。

这是明确 Accepted Limitation，而不是假装完全解决。

------

# 7. Bad Case

## Real Bad Case 1 — GovernedToolInvoker 变成第二套 Tool Runtime

Luna 初版虽然叫：

```text
GovernedToolInvoker
```

但实际自己承担了部分 Governance。

这会产生：

```text
Model-selected Tool
→ canonical Runtime A

Stage8 programmatic Tool
→ custom Runtime B
```

以后 Approval、Claim、UNKNOWN、Idempotency 很容易分叉。

Sol 最后把它收敛成：

```text
薄 facade
→ existing ToolRegistry
→ existing Governance
→ existing Durable Approval
→ existing Execution Claim
→ ToolExecutionService
```

这是非常适合面试讲的 Architecture Bad Case。

------

## Real Bad Case 2 — 任意 APPROVED TestPlan 可以放行执行

初版执行 Gate 不够严格。

潜在情况：

```text
TestPlan v1 → APPROVED

当前实际 TestPlan = v2
```

如果代码只判断：

```text
exists APPROVED TEST_PLAN review
```

那么旧 Review 可以错误批准新 Plan。

最终修成精确匹配：

```text
mission_id
subject_id
version
digest
```

------

## Real Bad Case 3 — Duplicate FAILED 重复建 Ticket Approval

`create_ticket` 是 non-idempotent。

如果：

```text
FAILED callback
→ PRODUCT
→ Approval A

重复 FAILED callback
→ PRODUCT
→ Approval B
```

就可能最终创建两个缺陷。

最终通过：

```text
callback terminal first-wins
+
DB triage claim
```

避免重复 downstream work。

------

## Real Bad Case 4 — Independent Triage API 接受 caller Evidence

初版：

```text
POST triage
{
    execution_id,
    evidence: caller_supplied
}
```

这让外部调用者可以伪造 Evidence Authority。

最后 Breaking Change 成：

```text
POST triage
{
    execution_id
}
```

系统自己从 durable state 重建证据。

------

## Real Bad Case 5 — Failure Triage Specialist 只是代码存在但没真正注册

Sol 审计时再次检查了这个问题，因为 WP1 曾经发生过类似情况。

最终：

```text
failure_triage
→ DEFAULT_AGENT_REGISTRY
→ failure_triage_adapter
```

真实可达，没有 fallback 到 `core_router`。

------

## Hypothetical Bad Case — Agent Run 等审批

假设：

```text
Failure Triage
→ create_ticket
→ APPROVAL_REQUIRED

while pending:
    sleep()
```

那么 Triage Run 又会变成长生命周期 Workflow。

所以正确：

```text
create durable pending approval
→ return
```

这是设计推演，不是最终实现中的遗留问题。

------

# 8. Truth / Owner / Completion Boundary

## Mission Truth

Owner：

```text
FeatureTestMission
MissionService
```

负责：

```text
EXECUTING
TRIAGING
COMPLETED
FAILED
```

状态推进仍走 Mission CAS。

------

## Agent Run Truth

Owner：

```text
AgentCore Runtime
RunCoordinator
AgentStateMachine
```

Run 不等待 external execution，也不等待 Ticket Approval。

------

## ExternalExecutionJob Truth

Owner：

```text
Stage8ExecutionService
stage8_external_execution_jobs
```

负责：

```text
PENDING
RUNNING
SUCCEEDED
FAILED
UNKNOWN
CANCELLED
```

------

## Tool Invocation Truth

Owner：

```text
ToolExecutionService
DurableToolInvocationService
```

负责：

```text
PREPARED
STARTED
COMMITTED
UNKNOWN
```

ExternalExecutionJob 的 UNKNOWN 不能替代这里的 UNKNOWN。

------

## Failure Triage Truth

Owner：

```text
FailureTriageResult
Stage8 Specialist Application layer
```

它表达：

```text
PRODUCT
TEST_DATA
ENVIRONMENT
TOOL_CHAIN
INFRASTRUCTURE
UNKNOWN
```

这是模型推理结果，不代表客观真理，只代表经过系统验证的业务分析。

------

## Evidence Truth

Source Identity Owner：

```text
Execution / Result / Case / Environment / Executor / Logs / Feature / TestPlan
```

模型只负责：

```text
classification
interpretation
confidence
```

不拥有 Evidence existence。

------

## Ticket Truth

`TicketDraft`：

```text
Stage8 business artifact
```

真实 Ticket：

```text
external Ticket Platform truth
```

`create_ticket` 仍通过 WP2 Tool Runtime 创建。

------

## Persistence Truth

WP3 新增：

```text
stage8_external_execution_jobs
```

Migration：

```text
0013_stage8_wp3
```

Final Gate 确认它是当前 Alembic head。

------

## WP3 真正完成

已真实实现：

```text
Approved current TestPlan exact binding

ExternalExecutionJob
PostgreSQL persistence

governed start_execution

Agent Run does not wait

Mission EXECUTING

callback result ingestion

execution_id → durable Mission binding

terminal first-wins

duplicate callback idempotency

success → COMPLETED

failure → TRIAGING

FailureEvidencePackage

Failure Triage Specialist

strict JSON / Pydantic / bounded repair

system-owned Evidence IDs

PRODUCT → typed TicketDraft

governed create_ticket

durable pending approval

Triage Run does not wait for approval

duplicate Ticket path prevention
```

Final Gate 对上述核心能力均确认通过。

------

## WP3 没完成

当前明确没有：

```text
callback HMAC / OAuth

TEST_DATA auto repair
business rerun

ticket approval 后的自动 asynchronous continuation

完整 ticket lifecycle

external start reconciliation worker

HA outbox worker

真实 remote executor

historical Failure RAG

environment auto reschedule
```

这些属于 Completion Boundary，面试时不能说已经完成。

------

# 9. 本 WP 最应该记住的五句话

第一句：

> **长生命周期测试任务属于 Mission / External Job，不属于 Agent Run。**

第二句：

> **Callback 是外部事实摄入，不是 Tool Call；主动外部副作用才走 Tool Runtime。**

第三句：

> **重复 callback 不只是状态幂等问题，还必须保证不会重复触发后续 non-idempotent Side Effect。**

第四句：

> **Failure Triage 可以推理根因，但 Evidence identity 必须由系统持有，不能让模型自己编证据。**

第五句：

> **Programmatic Tool Invocation 可以有新的 facade，但不能有新的 Execution Authority。**